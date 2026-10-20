// 브리핑 "먼저 챙길 일"의 비서 정리 스위치 (2026-10-19, 사용자 지시: 먼저 챙길 일만 끔). 의존 없는 순수 함수라 tools/briefing_switch_check.mjs 가 Node로 그대로 시험한다.
// 기본은 꺼짐: 화면이 비서를 묻지 않고 프로그램 원문 줄만 보인다. 문장 틀마다 서술어를 프로그램이 정하는 방식으로 바꾸는 동안의 임시 상태다.
// 다시 켜려면 화면 서버를 NEXT_PUBLIC_MOM_BRIEFING_LLM=1 로 켠다.

export const briefingLlmOn = (flag: string | undefined): boolean => flag === '1';

/** 비서에게 묻는 키. 꺼짐이거나 교대·줄이 없으면 '' (= 묻지 않는다). 켜짐이면 예전 useBriefingText 의 키와 같은 값이다. */
export const briefingAskKey = (on: boolean, shift: string | undefined, groups: unknown[]): string => (on && shift && groups.length ? JSON.stringify([shift, groups]) : '');
