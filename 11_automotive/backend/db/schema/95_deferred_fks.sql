-- =====================================================================
-- 95_deferred_fks.sql — 서로를 가리키는 외래 키 (순환)
--   notification.wo_no            → maintenance_work_order
--   maintenance_work_order.trigger_notification_id → notification   (반복 알람 2단계 원인 점검)
--   work_record.cause_check_notification_id        → notification   (다른 공정 원인 점검 간이 기록)
-- 한 트랜잭션 안에서 순서 없이 넣을 수 있게 DEFERRABLE INITIALLY DEFERRED로 건다
-- (생성기 CSV 적재·워크플로 함수 둘 다 커밋 때 확인된다).
-- =====================================================================

ALTER TABLE maintenance_work_order
    ADD CONSTRAINT fk_wo_trigger_notification FOREIGN KEY (trigger_notification_id)
        REFERENCES notification (notification_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE work_record
    ADD CONSTRAINT fk_work_record_cause_check FOREIGN KEY (cause_check_notification_id)
        REFERENCES notification (notification_id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE notification
    DROP CONSTRAINT IF EXISTS notification_wo_no_fkey,
    ADD CONSTRAINT fk_notification_wo FOREIGN KEY (wo_no)
        REFERENCES maintenance_work_order (wo_no) DEFERRABLE INITIALLY DEFERRED;
