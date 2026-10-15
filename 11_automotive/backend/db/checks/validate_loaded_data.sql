-- =====================================================================
-- validate_loaded_data.sql — 생성기 데이터를 넣은 뒤 돌리는 점검 (설계서 9장 + 이 설계의 규칙)
-- 트리거는 "상태가 바뀌는 순간"만 막으므로, 과거 기록을 INSERT로 한꺼번에 넣은 데이터는 여기서 확인한다.
-- 결과: 점검마다 위반 건수. 0이 아니면 생성기나 적재 순서를 고친다 (NFR-DATA-04·05).
-- 쓰는 법: psql -d mom -f db/checks/validate_loaded_data.sql
-- =====================================================================
WITH checks(no, rule, violations) AS (
  -- R-03 작업기록서 수리 시간 = DOWN 구간 길이 (오차 1분 이내)
  SELECT 1, 'R-03 수리 시간 = DOWN 구간', count(*) FROM work_record w
    JOIN maintenance_work_order m USING (wo_no) JOIN equipment_state_log s ON s.alarm_event_id = m.alarm_event_id
   WHERE w.record_type = 'FULL' AND w.status IN ('CONFIRMED','CHECKED') AND s.state_code = 'DOWN'
     AND abs(w.repair_min - s.duration_min) > 1
  UNION ALL
  -- R-01 정지 등급 알람 1건 ↔ DOWN 1구간 (OP-30·다른 공정 모두). 충돌 연쇄 108 → 994 → 992는 마지막 992만 DOWN (2026-10-13)
  SELECT 2, 'R-01 정지 알람마다 DOWN 구간', count(*) FROM alarm_event a
   WHERE a.severity_at_event = 'STOP' AND a.is_injected = false
     AND NOT EXISTS (SELECT 1 FROM alarm_event nx WHERE nx.prev_alarm_event_id = a.alarm_event_id)
     AND NOT EXISTS (SELECT 1 FROM equipment_state_log s WHERE s.alarm_event_id = a.alarm_event_id AND s.state_code = 'DOWN')
  UNION ALL
  -- R-05 로트 완료 수량 = OP-50 양품 + 재작업 = 합격 입고 수량. 폐기한 부품은 이미 양품에서 빠져 있다 (생성기·DOC-06 §4)
  SELECT 3, 'R-05·R-69 합격 입고 = 완료 수량', count(*) FROM production_lot l
    JOIN inventory_txn t ON t.source_kind = 'LOT_PASS' AND t.fg_lot_no = l.lot_no
   WHERE l.status = 'PASSED' AND NOT EXISTS (SELECT 1 FROM lot_hold h WHERE h.lot_no = l.lot_no AND h.result = 'RELEASED')
     AND t.qty_change <> fn_lot_completed_qty(l.lot_no)
  UNION ALL
  -- R-07 OP-10 투입은 로트의 투입 교대 안
  SELECT 4, 'R-07 OP-10 실적 교대 = 로트 투입 교대', count(*) FROM operation_report r JOIN production_lot l USING (lot_no)
   WHERE r.process_code = 'OP-10' AND r.shift_id <> l.input_shift_id
  UNION ALL
  -- R-08 작업지시 수량 = 로트 투입 합 (끝난 작업지시). 진행 중·취소는 ≤ (9/30 끝에 투입 중인 작업지시가 있다)
  SELECT 5, 'R-08 로트 투입 합 = 작업지시 수량', count(*) FROM production_order o
    JOIN LATERAL (SELECT coalesce(sum(input_qty), 0) AS s FROM production_lot l WHERE l.order_no = o.order_no) x ON true
   WHERE o.status = 'DONE' AND x.s <> o.order_qty OR o.status IN ('IN_PROGRESS','CANCELLED') AND x.s > o.order_qty
  UNION ALL
  -- R-12 교대 보고서 2개 실적 합 = 일일 보고서 실적
  SELECT 6, 'R-12 교대 실적 합 = 일일 실적', count(*) FROM daily_report d
   WHERE d.actual_qty <> (SELECT coalesce(sum(r.actual_qty), 0) FROM shift_report r JOIN shift s USING (shift_id) WHERE s.work_date = d.work_date)
  UNION ALL
  -- R-14 BLOCKED 구간마다 그 시각 뒤 재공이 한도
  SELECT 7, 'R-14 BLOCKED 때 뒤 재공 = 한도', count(*) FROM equipment_state_log s JOIN equipment e USING (equipment_id)
    JOIN wip_buffer b ON b.from_process_code = e.process_code
   WHERE s.state_code = 'BLOCKED' AND NOT EXISTS (
         SELECT 1 FROM wip_log w WHERE w.buffer_code = b.buffer_code AND w.wip_qty >= b.limit_qty
            AND w.logged_at BETWEEN s.start_at - interval '5 minutes' AND coalesce(s.end_at, s.start_at) + interval '5 minutes')
  UNION ALL
  -- R-32 확정된 작업기록(잠금·표지 필요)은 9단계 모두 체크
  SELECT 8, 'R-32 확정 기록의 잠금·표지 9단계', count(*) FROM work_record w
   WHERE w.safety_block_required AND w.status IN ('CONFIRMED','CHECKED')
     AND (SELECT count(*) FROM work_record_check c WHERE c.record_no = w.record_no AND c.check_kind = 'LOTO' AND c.is_checked) < 9
  UNION ALL
  -- R-35 문서마다 current_version까지 버전이 빠짐없이 있어야 함
  SELECT 9, 'R-35 문서 버전 v0~current 있음', count(*) FROM (
      SELECT 'WORK_ORDER' AS dt, wo_no AS k, current_version AS cv FROM maintenance_work_order
      UNION ALL SELECT 'WORK_RECORD', record_no, current_version FROM work_record
      UNION ALL SELECT 'SHIFT_REPORT', shift_id, current_version FROM shift_report
      UNION ALL SELECT 'DAILY_REPORT', work_date::text, current_version FROM daily_report
      UNION ALL SELECT 'PM_RECORD', pm_record_id::text, current_version FROM pm_record
      UNION ALL SELECT 'SHIPMENT', shipment_no, current_version FROM shipment) d
   WHERE (SELECT count(*) FROM document_revision r WHERE r.doc_type = d.dt AND r.doc_key = d.k AND r.version_no <= d.cv) <> d.cv + 1
  UNION ALL
  -- R-25 로트 판정은 측정할 부품을 모두 잰 뒤
  SELECT 10, 'R-25 합격 로트의 측정 부품 모두 있음', count(*) FROM production_lot l JOIN inspection_plan p USING (lot_no)
   WHERE p.judgement = 'PASS' AND EXISTS (
         SELECT 1 FROM fn_planned_parts(l.lot_no) part
          WHERE NOT EXISTS (SELECT 1 FROM inspection_result r WHERE r.lot_no = l.lot_no AND r.part_seq = part AND r.use_for_judgement))
  UNION ALL
  -- R-36 교대 보고서 확정자 = 그 교대 반장
  SELECT 11, 'R-36 교대 보고서 확정자', count(*) FROM shift_report r JOIN shift s USING (shift_id)
   WHERE r.confirmed_by IS NOT NULL AND r.confirmed_by <> s.supervisor_user_id
  UNION ALL
  -- R-67 출하 로트는 합격·해제, 출하 시각 > 합격 시각
  SELECT 12, 'R-67 출하 로트 합격·시각', count(*) FROM shipment_line sl JOIN shipment s USING (shipment_no) JOIN production_lot l USING (lot_no)
   WHERE s.status <> 'DRAFT' AND (l.status NOT IN ('PASSED','RELEASED') OR s.shipped_at <= sl.lot_passed_at)
  UNION ALL
  -- R-10 공구 누적 = 마지막 사용 기록 누적 (교체 뒤 사용이 있으면)
  SELECT 13, 'R-10 공구 누적 = 마지막 사용 기록', count(*) FROM tool tl
    JOIN LATERAL (SELECT u.cum_after FROM tool_usage u WHERE u.tool_id = tl.tool_id ORDER BY u.recorded_at DESC, u.seg DESC LIMIT 1) u ON true
   WHERE (tl.last_changed_at IS NULL OR (SELECT max(recorded_at) FROM tool_usage x WHERE x.tool_id = tl.tool_id) > tl.last_changed_at)
     AND u.cum_after <> tl.cum_usage
  UNION ALL
  -- R-11 재고 수량 = 거래 합 (트리거가 유지하지만, 다른 경로로 바뀌지 않았는지)
  SELECT 14, 'R-11 재고 수량 = 거래 합', count(*) FROM inventory_item i
   WHERE i.on_hand_qty <> (SELECT coalesce(sum(t.qty_change), 0) FROM inventory_txn t WHERE t.item_no = i.item_no)
  UNION ALL
  -- R-24 센서 값은 센서가 있는 설비만
  SELECT 15, 'R-24 센서 값은 OP-30만', count(*) FROM sensor_sample s JOIN equipment e USING (equipment_id) WHERE NOT e.has_sensor
  UNION ALL
  -- R-88 이월 = 야간만 max(0, 같은 날 주간 목표 − 주간 실적(확정 보고서 값, 없으면 OP-50 GQ+RQ)). 주간 기록이 없으면 0
  SELECT 16, 'R-88 야간 이월 = max(0, 주간 목표 − 주간 실적)', count(*) FROM shift n
    LEFT JOIN shift d ON d.work_date = n.work_date AND d.shift_type = 'DAY'
    LEFT JOIN shift_report dr ON dr.shift_id = d.shift_id AND dr.status IN ('CONFIRMED','REVISED')
   WHERE n.shift_type = 'NIGHT'
     AND n.carry_over_qty <> CASE WHEN d.shift_id IS NULL
                                       OR NOT (EXISTS (SELECT 1 FROM shift_report r WHERE r.shift_id = d.shift_id)
                                               OR EXISTS (SELECT 1 FROM operation_report o WHERE o.shift_id = d.shift_id))
                                  THEN 0
                                  ELSE greatest(0, d.target_qty - coalesce(dr.actual_qty, fn_shift_actual_qty(d.shift_id))) END
  UNION ALL
  -- R-88 교대 보고서 목표 = 총 목표 (목표 + 이월)
  SELECT 17, 'R-88 교대 보고서 목표 = 총 목표', count(*) FROM shift_report r JOIN shift s USING (shift_id)
   WHERE r.target_qty <> s.target_qty + s.carry_over_qty
  UNION ALL
  -- R-88 일일 보고서 목표 = 하루 목표 (180 고정, 이월을 더하지 않음)
  SELECT 18, 'R-88 일일 보고서 목표 = 하루 목표 (이월 없음)', count(*) FROM daily_report r JOIN work_day d USING (work_date)
   WHERE r.target_qty <> d.daily_target_qty
  UNION ALL
  -- R-23 MAINT 구간은 예방 정비 기록을 가리킨다. 비우면 반복 알람 2단계 원인 점검 — 같은 설비 작업기록서가 그 시간을 가진다
  SELECT 19, 'R-23 MAINT 구간 = 예방 정비 기록 또는 원인 점검 작업기록', count(*) FROM equipment_state_log s
   WHERE s.state_code = 'MAINT' AND s.pm_record_id IS NULL
     AND NOT EXISTS (SELECT 1 FROM work_record w WHERE w.equipment_id = s.equipment_id
                       AND w.start_at < coalesce(s.end_at, 'infinity') AND coalesce(w.end_at, 'infinity') > s.start_at)
  UNION ALL
  -- 로트 폐기 수량 = 폐기 처분한 불량 수 (production_lot.scrap_qty, 5.B.3)
  SELECT 20, '로트 폐기 수량 = 폐기 불량 합', count(*) FROM production_lot l
   WHERE l.status <> 'SCRAPPED'
     AND l.scrap_qty <> (SELECT coalesce(sum(d.qty), 0) FROM defect_record d WHERE d.lot_no = l.lot_no AND d.disposition = 'SCRAP')

)
SELECT no, rule, violations, CASE WHEN violations = 0 THEN 'OK' ELSE '확인 필요' END AS result FROM checks ORDER BY no;

-- 설계서 9장 범위 점검 (막는 규칙이 아니라 생성 결과 확인용 — 참고). 생성기 validate.py가 같은 범위를 자기 셈법
-- (근무 시간·근무일 기준)으로 이미 점검한다 (9월 87줄 실패 0). 여기 값은 휴무일·밤 시간까지 넣어 셈이 달라 낮게 나올 수 있다
SELECT 'R-60 VF-2 하루 상태 변화 60~120회' AS rule,
       min(n) AS min_per_day, max(n) AS max_per_day
  FROM (SELECT equipment_id, (start_at AT TIME ZONE 'Asia/Seoul')::date AS d, count(*) AS n
          FROM equipment_state_log s JOIN work_day w ON w.work_date = (s.start_at AT TIME ZONE 'Asia/Seoul')::date
         WHERE equipment_id LIKE 'VF2-%' AND w.is_workday GROUP BY 1, 2) x
UNION ALL
SELECT 'R-61 VF-2 RUN 비율 55~75% (×100)',
       round(100 * sum(duration_min) FILTER (WHERE state_code = 'RUN') / nullif(sum(duration_min), 0)), NULL
  FROM equipment_state_log WHERE equipment_id LIKE 'VF2-%'
UNION ALL
SELECT 'R-62 전체 불량률 0.5~1.0% (×100)',
       round(10000.0 * (SELECT sum(qty) FROM defect_record) / nullif(sum(pq), 0)) / 100, NULL
  FROM operation_report WHERE process_code = 'OP-10'
UNION ALL
SELECT 'R-63 조작 안내 알람 비율 70% 이상',
       round(100.0 * count(*) FILTER (WHERE severity_at_event = 'GUIDE') / nullif(count(*), 0)), NULL FROM alarm_event;
