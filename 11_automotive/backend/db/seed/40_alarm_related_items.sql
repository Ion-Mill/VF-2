-- 알람 관련 재고 품목 (논리 ERD 5.C.8, R-89). 알람 코드집·재고 품목이 아직 없으면 0줄 — 목업·생성기 적재 뒤 다시 부른다
SELECT fn_seed_alarm_related_items() AS alarm_related_items;
