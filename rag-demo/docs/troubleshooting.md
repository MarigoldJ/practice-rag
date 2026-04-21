# 장애 대응 및 트러블슈팅 가이드

## 1. 자주 발생하는 장애 상황

### 1.1 API 서버 응답 지연

**증상**: API 응답 시간이 평소(200ms 이하)보다 크게 증가하여 1초 이상 걸리는 현상

**주요 원인**:
- 데이터베이스 슬로우 쿼리 발생
- Redis 캐시 미스율 급증
- 동시 접속자 수 급증
- 메모리 부족으로 인한 스왑 발생

**확인 방법**:
1. Grafana 대시보드에서 API 응답 시간 그래프 확인
2. PostgreSQL 슬로우 쿼리 로그 확인: `SELECT * FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '5 seconds';`
3. Redis 상태 확인: `redis-cli info stats | grep hit`
4. 서버 메모리 확인: `free -h`

**대응 방법**:
- 슬로우 쿼리가 원인인 경우 → 쿼리 최적화 또는 인덱스 추가
- 캐시 미스율이 높은 경우 → 캐시 워밍업 수행
- 동시 접속 급증인 경우 → 오토스케일링 확인 또는 수동 스케일아웃

### 1.2 502 Bad Gateway 에러

**증상**: 사용자에게 502 에러가 표시되며 서비스 이용이 불가

**주요 원인**:
- 백엔드 API 서버가 다운된 상태
- Nginx와 백엔드 서버 간 연결 실패
- 백엔드 서버의 포트 설정 불일치

**확인 방법**:
1. 백엔드 파드 상태 확인: `kubectl get pods -l app=backend`
2. 파드 로그 확인: `kubectl logs -l app=backend --tail=100`
3. Nginx 에러 로그 확인: `/var/log/nginx/error.log`

**대응 방법**:
- 파드가 CrashLoopBackOff 상태인 경우 → 로그에서 에러 원인 파악 후 수정
- 파드가 정상인데 502인 경우 → Nginx 설정의 upstream 주소 확인
- OOM으로 파드가 죽은 경우 → 리소스 제한 값 조정

### 1.3 데이터베이스 연결 실패

**증상**: "could not connect to server" 또는 "too many connections" 에러 발생

**주요 원인**:
- 데이터베이스 서버 다운
- 커넥션 풀 고갈
- 네트워크 연결 문제
- 데이터베이스 최대 연결 수 초과

**확인 방법**:
1. DB 서버 상태 확인: `pg_isready -h db-host -p 5432`
2. 현재 연결 수 확인: `SELECT count(*) FROM pg_stat_activity;`
3. 커넥션 풀 상태 확인 (애플리케이션 로그)

**대응 방법**:
- DB 서버 다운 시 → 장애 복구 절차 진행 (운영팀 연락)
- 커넥션 풀 고갈 시 → 유휴 연결 정리, 풀 크기 조정
- max_connections 초과 시 → 불필요한 연결 종료 후 설정 값 조정

### 1.4 Celery 워커 태스크 적체

**증상**: 비동기 작업(알림 발송, 리포트 생성 등)이 지연되거나 처리되지 않음

**주요 원인**:
- 워커 프로세스가 종료된 상태
- Redis(브로커) 메모리 부족
- 특정 태스크에서 무한 루프 또는 데드락 발생

**확인 방법**:
1. Flower 대시보드에서 워커 상태 확인
2. 큐에 적체된 태스크 수 확인: `redis-cli llen celery`
3. 워커 로그 확인: `kubectl logs -l app=worker --tail=200`

**대응 방법**:
- 워커 재시작: `kubectl rollout restart deployment/worker`
- Redis 메모리 부족 시 → 완료된 태스크 결과 정리 또는 메모리 증설
- 문제 태스크 식별 후 수동 취소: Flower에서 해당 태스크 revoke

## 2. 로그 확인 포인트

### 2.1 로그 위치 및 접근 방법

| 로그 종류 | 확인 방법 |
|-----------|----------|
| 백엔드 API 로그 | `kubectl logs -l app=backend --tail=200` |
| 워커 로그 | `kubectl logs -l app=worker --tail=200` |
| Nginx 접근 로그 | `/var/log/nginx/access.log` |
| Nginx 에러 로그 | `/var/log/nginx/error.log` |
| PostgreSQL 로그 | `/var/log/postgresql/postgresql-14-main.log` |
| Redis 로그 | `redis-cli monitor` (실시간) |

### 2.2 로그에서 확인해야 할 핵심 키워드

에러 상황별로 아래 키워드를 검색합니다:

- **서버 에러**: `ERROR`, `CRITICAL`, `Traceback`, `Exception`
- **인증 문제**: `401`, `403`, `Unauthorized`, `Forbidden`, `JWT`
- **DB 문제**: `OperationalError`, `IntegrityError`, `deadlock`, `timeout`
- **메모리 문제**: `OOMKilled`, `MemoryError`, `Cannot allocate memory`
- **네트워크 문제**: `ConnectionRefused`, `ConnectionTimeout`, `ECONNRESET`

### 2.3 Kibana를 이용한 로그 분석

1. Kibana에 접속합니다: `https://kibana.internal.example.com`
2. Discover 탭에서 시간 범위를 장애 발생 시점 전후로 설정합니다.
3. 필터 조건을 추가합니다:
   - `level: ERROR` - 에러 로그만 필터
   - `service: backend` - 특정 서비스 로그만 필터
   - `trace_id: xxx` - 특정 요청의 전체 흐름 추적

## 3. 주요 대응 절차

### 3.1 캐시 초기화

Redis 캐시에 잘못된 데이터가 저장되어 문제가 발생하는 경우:

```
# 특정 키 패턴의 캐시만 삭제
redis-cli KEYS "cache:api:*" | xargs redis-cli DEL

# 전체 캐시 초기화 (주의: 세션 데이터도 함께 삭제됨)
redis-cli FLUSHDB

# 캐시만 별도 DB를 사용하는 경우
redis-cli -n 1 FLUSHDB
```

주의사항:
- 운영 환경에서 FLUSHALL은 절대 사용하지 않습니다.
- 캐시 초기화 후 일시적으로 DB 부하가 증가할 수 있으므로 모니터링에 주의합니다.
- 가능하면 특정 키 패턴만 선택적으로 삭제합니다.

### 3.2 워커 재시작

워커 프로세스에 문제가 있는 경우:

```
# 워커 디플로이먼트 재시작
kubectl rollout restart deployment/worker

# 재시작 상태 확인
kubectl rollout status deployment/worker

# 특정 워커 파드만 삭제하여 재시작
kubectl delete pod worker-xxxxx
```

재시작 후 확인 사항:
- Flower 대시보드에서 워커가 정상 등록되었는지 확인
- 적체된 태스크가 정상적으로 처리되기 시작했는지 확인
- 에러 로그가 더 이상 발생하지 않는지 확인

### 3.3 데이터베이스 긴급 조치

DB 커넥션이 부족한 경우 유휴 연결을 강제 종료합니다:

```sql
-- 5분 이상 유휴 상태인 연결 종료
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < now() - interval '5 minutes'
AND pid <> pg_backend_pid();
```

장시간 실행 중인 쿼리를 확인하고 필요 시 종료합니다:

```sql
-- 1분 이상 실행 중인 쿼리 확인
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
AND query_start < now() - interval '1 minute';

-- 특정 쿼리 강제 종료
SELECT pg_terminate_backend(대상_pid);
```

### 3.4 서비스 전체 재시작 (최후의 수단)

위의 개별 대응으로 해결되지 않는 경우, 전체 서비스를 재시작합니다.

```
# 1. 워커 먼저 중지 (새 태스크 수신 방지)
kubectl scale deployment/worker --replicas=0

# 2. 백엔드 재시작
kubectl rollout restart deployment/backend

# 3. 백엔드 정상 확인 후 워커 재시작
kubectl scale deployment/worker --replicas=3

# 4. 프론트엔드는 정적 파일이므로 보통 재시작 불필요
# 필요한 경우 Nginx만 리로드
sudo nginx -s reload
```

## 4. 장애 대응 체크리스트

장애 발생 시 아래 체크리스트를 순서대로 확인합니다:

1. [ ] 장애 인지 및 팀 공유 (Slack #incident 채널)
2. [ ] 영향 범위 파악 (어떤 기능이 영향 받는지)
3. [ ] 로그에서 에러 원인 확인
4. [ ] 긴급 대응 (캐시 초기화, 서비스 재시작, 롤백 등)
5. [ ] 서비스 정상화 확인
6. [ ] 사용자/관련 팀에 복구 안내
7. [ ] 포스트모템 작성 (장애 발생 후 3일 이내)
8. [ ] 재발 방지 대책 수립 및 적용
