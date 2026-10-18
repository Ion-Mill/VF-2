# 외부 Claude 챗봇 백엔드 이식 묶음 (2026-10-16)

- 만든 날: 2026-10-16
- 원본: 이 묶음을 만든 프로젝트의 `backend/`와 `requirements.txt` (같은 날 복사)
- 범위: **백엔드만** (사용자 결정, 2026-10-16). 받는 프로젝트에 화면·가상 데이터 생성기·가상 사내 문서가 이미 있다
- 설명서: 원본 프로젝트의 `research_notes/외부LLM_챗봇_이식_패키지분석_20261015.md` 9.8절 (묶음에는 넣지 않음)

## 1. 들어 있는 것과 넣지 않은 것

| 구분 | 내용 |
|---|---|
| 들어 있음 | `backend/` 전체 317개 파일(`__pycache__`·`.pytest_cache`·`backend/eval/history/` 뺌), `requirements.txt`, 이 `MANIFEST.md` |
| 넣지 않음 | `.env`와 그 사본, 실제 데이터, 화면 `src/`, 가상 데이터 생성기 `simulator/`, 가상 사내 문서, 평가 기록, `scripts/`, Haas 원문·번역본 |
| 비밀값 검사 | 묶음 안 `.env*` 0개. 키 꼴(`sk-ant-`·`LLM_API_KEY=`)이 걸린 곳은 시험 파일 3개(`test_claude_cli.py`·`test_claude_client.py`·`test_step_log.py`)뿐이고, 모두 "키가 새지 않는지" 보는 가짜 값이다(`sk-ant-zzz`, `SECRETSECRET`, `FAKE` 등) |

## 2. 받는 쪽이 저장소 루트 기준으로 둘 것

`backend/config.py`는 `backend/`의 바로 위 폴더를 루트(`ROOT`)로 보고 아래 경로를 읽는다. 받는 프로젝트의 위치가 다르면 그 줄을 고친다.

| 코드 | 읽는 경로 (`ROOT` 기준) | 무엇 |
|---|---|---|
| `config.py` `SIM_OUT` | `simulator/out/` | 가상 운영 데이터 CSV |
| `config.py` `SIM_MASTERS` | `simulator/masters/` | 설비·알람 등 기준표 CSV |
| `config.py` `SIM_CONFIG` | `simulator/config.json` | 가상 데이터 설정 |
| `config.py` `DOCS_DIR` | `참고문서/매뉴얼/11_automotive/가상사내문서/` | 사내 문서 DOC-01~07·용어집 (검색 코퍼스, 195조각) |
| `config.py` (`.env` 읽기) | `.env` | 설정·스위치 (받는 쪽이 직접 만듦) |
| `demo_state.py` `SCENARIO_DIR` | `simulator/scenarios/` | 시연 사건 |
| `eval/run_eval.py` | `simulator/out/`, `simulator/masters/` | 평가 도구 (앱 실행에는 필요 없음) |

저장소 밖 기본 폴더도 있다. 받는 PC에 맞게 환경변수로 바꾼다.

| 코드 기본값 | 바꾸는 환경변수 | 무엇 |
|---|---|---|
| `C:\llm\claude_cli_cwd` (`llm/claude_cli.py`) | `MOM_CLAUDE_CWD` | `claude -p`를 돌릴 빈 작업 폴더 |
| PATH의 `claude` → Cursor·VS Code 확장 폴더 | `MOM_CLAUDE_BIN` | Claude Code 실행 파일 |
| `C:\llm\logs` (`services/steplog.py`) | `STEP_LOG_DIR` | 단계별 로그 (`STEP_LOG=1`일 때만 씀) |

## 3. 받는 쪽 순서

1. 파이썬 3.12에서 `pip install -r requirements.txt` (원본 기준 fastapi 0.142.2, uvicorn 0.54.0, pydantic 2.13.5, httpx 0.28.1, pytest 9.1.1). `anthropic` 패키지는 앱 경로에 필요 없다.
2. Claude Code CLI를 설치하고 구독으로 로그인한다. `claude --version`, `claude auth status`로 확인한다. 앱은 자식 프로세스에서 `CLAUDE*`·`ANTHROPIC*` 변수를 빼므로 API 키만으로는 인증되지 않는다.
3. 루트에 `.env`를 직접 만든다. 외부 Claude에 필요한 값:
   - `EXTERNAL_LLM_APP=1` (0이면 외부로 한 글자도 안 나감)
   - `LLM_ENABLED=1`, `LLM_JOBS=write,route` (꺼져 있으면 LLM을 부르지 않고 규칙·기본 문장만 씀)
   - 원본 앱이 켠 동작 스위치: `NUM_MATCH=value`, `PARSE_V2=1`, `ROUTE_POLICY=llm_guarded`, `DOC_GATE=tiered`, `PARSE_V3=1`, `SPLIT_Q=1`, `PARSE_V4=1`, `PARSE_V5=1`, `PARSE_V6=1`, `PARSE_V7=1`, `FOLLOWUP=1`, `PARSE_V8=1`, `FOLLOWUP_V2=1`, `PARSE_V9=1`, `FLOW_V9=1`, `BLOCKS_V2=1`, `PARSE_V10=1`, `FLOW_V10=1`, `BLOCKS_V3=1`, `DOC_WRITE=1`, `PARSE_V11=1`, `LEAD_V12=1`, `TERM_V13=1`, `ANSWER_GATE_V17=1`, `TABLE_FILL_V18=1`, `RETRIEVAL=bm25`
   - 필요하면 `MOM_CLAUDE_CWD`, `MOM_CLAUDE_BIN`, `EXTERNAL_PROC_LIMIT`(기본 8)
   - 쓰지 않는 값: `THINK_APP`(로컬 Qwen 전용), `LLM_URL`·`LLM_MODEL`·`LLM_API_KEY`(로컬 Qwen 서버용), `DATABASE_URL`(pgvector를 쓸 때만)
4. `uvicorn backend.app:app --host 127.0.0.1 --port 8000`으로 켠다. `/api/health`의 `external_llm.server_switch`·`available`이 `true`인지 본다.
5. `pytest backend/tests`로 확인한다.

**Claude를 고르는 방법:** 이 코드 그대로는 질문 요청 본문의 `"llm": "claude"`가 그 요청만 Claude로 보낸다(`app.py`). 이 칸이 없으면 로컬 LLM 경로다. `API명세서_v1.md`의 AST-02 요청(`question`, `context`)에는 `llm` 칸이 없으므로, Claude만 쓰려면 받는 쪽 서버가 요청을 넘길 때 이 값을 붙이도록 고친다(화면에서 보내게 하지 않는다).

## 4. 알려진 예외

| 시험 | 까닭 |
|---|---|
| `test_req_map.py` | 기획 문서가 `기획서 최종본/`이나 `참고문서/매뉴얼/11_automotive/`에 있어야 한다 |
| `test_step_log.py` | 기본 로그 폴더 `C:\llm\logs`를 확인하고, 루트의 `scripts/step_log_view.py`를 읽는다 |
| `test_run_blind_sb.py` | 루트의 `scripts/eval/run_blind_sb.py`를 읽는다 |
| 사내 문서·가상 데이터를 읽는 시험 | 2절의 경로에 파일이 있어야 한다 |

- 시험은 Claude CLI를 가짜 실행기로 바꿔 돌린다. 실제 외부 호출은 하지 않는다.
- 외부 Claude로 나가는 것은 질문, 사내 문서 조각, 운영 조회 결과다. 원본에서는 모두 가상 데이터였다. 실제 데이터를 쓰는 프로젝트는 반출 승인을 먼저 정한다.

## 5. 파일 목록

줄 수와 SHA-256은 Python으로 계산했다. 이 `MANIFEST.md`는 목록에 넣지 않았다.

| 파일 | 줄 수 | SHA-256 |
|---|---|---|
| backend/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/app.py | 345 | bb31d8065927a78bddebcbbd8ac84fe58e84a803e22d0cba5a02e7e5d6d5b504 |
| backend/auth/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/auth/permissions.py | 79 | fab100408a63024b1a4de4c2d25fdcd6e7243d63c39c6a882b60504fba58beed |
| backend/config.py | 268 | 7515eff8af35051f53be12705fa317e08c3cbf3f717af3cef8af113c2771518c |
| backend/demo_state.py | 162 | 05d3ba06dc74a288fa2a4dccf56ed946a0950d77c4c590b9b2774c74e44effa1 |
| backend/errors.py | 86 | 62ee8f7ecb0b4319b63531ef79186d9fe9b0bbc6b80a5e641290f6bd8d247aea |
| backend/eval/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/eval/build_abstain_pool.py | 34 | ed9a42a95aa40dea59ba11312c425751553c585726db883ce1b0207c8b3b9f8d |
| backend/eval/compare_runs.py | 102 | ae06b992327ec37e3b8e78f7026ba156d907df90cebbd2542d4ae69caee25057 |
| backend/eval/qa_abstain_pool.json | 1308 | a76390e48136b664cdf893fed6890cf0cb142324a3b530eb12001d9778ac0fd1 |
| backend/eval/qa_followup.json | 23 | 1946a5aad7d9757bd35da5dfb164fd23bd8f7237ef0c38c19d443ed2bfdf1540 |
| backend/eval/qa_holdout.json | 27 | 30acef5cd158547ec314220efe58e3e1bf90845ae885d3f7e793074ac7c9631a |
| backend/eval/qa_holdout_b.json | 23 | 00b62b00134f9af3f81ab6adb0a3d03a6c2bf940f1303560e17cb6d11f1c2b66 |
| backend/eval/qa_holdout_c.json | 30 | 80ea39dabc5344132194314a5d2012c194f868fabf8a5cff1ff225588c7a7020 |
| backend/eval/qa_holdout_cmp30.evidence.json | 59 | 172d6b22363ecb637418212c641eb20e8cfbcdf61c8082b03821189b4673c4ea |
| backend/eval/qa_holdout_cmp30.json | 212 | 69144ef1d7f2d3b656888f7b6c2354dec7a2d51d0d6c30fbedf0f1d6e10f9d4d |
| backend/eval/qa_holdout_d.json | 25 | 4b0ecb0262f9ab805c3445bae94b5f9435463b6919253e4591fa1691dd6ac2da |
| backend/eval/qa_holdout_e.evidence.json | 906 | e39d5068f8beb896cf9d4f7b9107747d874c07e2bf1a647caac73194530a4213 |
| backend/eval/qa_holdout_e.json | 1136 | bf153dc7c2a9d1343adbfb5c7fe8de8569bae6f7e2f6051ea1fcc76c6bea15db |
| backend/eval/qa_holdout_e2.evidence.json | 17 | fe8127fdbb37f7e24ffde2b1d629a6117dbb91fb93632b25de91af7864b37232 |
| backend/eval/qa_holdout_e2.json | 1118 | a562a4dddfa031d80f8cb4035b7a1f7c6ffdb366c16b950e5c1a6cdddf4c28ce |
| backend/eval/qa_holdout_e3.evidence.json | 585 | ac27d3b0f3cf2a56e4c23eff80c6db0b6c28b03aee43c301d8a2faa09c84a0e4 |
| backend/eval/qa_holdout_e3.json | 1112 | ca25808353abd2b705ec02c80bf3025345b254e3a3fc1b1ec2a7869d5374293c |
| backend/eval/qa_holdout_e4.evidence.json | 1280 | 46d0fdb6a956c31f844c462ae60a9089e1b06fe471f927409d7b8cf6014dfbae |
| backend/eval/qa_holdout_e4.json | 1079 | f49b08715803b8bdd84394d4ae8d49105908149a5b8ff64eee68079b411831c3 |
| backend/eval/qa_holdout_e5.evidence.json | 17 | 8e555652339d8dc25211d20fa23d570af2d038a46cc6704676242d28d706940a |
| backend/eval/qa_holdout_e5.json | 105 | 256de13ae28ac06b49bc5cc8b6d2c3de0f1ac699b0d9ac793b1bcd99568c98b7 |
| backend/eval/qa_holdout_e6.evidence.json | 259 | dfed360b8df44cc2beb950c00c7b3583c0074e9cce595168e4886a3e22b1dea2 |
| backend/eval/qa_holdout_e6.json | 1141 | 73041082dc20bf9ba5bdd0e2767c79e1591d817a606fb6a9117e99f3bb4e8b9b |
| backend/eval/qa_holdout_e7.evidence.json | 19 | bc2cee862ead47be2b9d8694f50629ee9a3a038e74815e47d8246017c62fa483 |
| backend/eval/qa_holdout_e7.json | 105 | d0185fb4c31da7c2a866bc8d458391b3e6c0b3be367e1a8e5e2478ec1d73e163 |
| backend/eval/qa_holdout_e8.evidence.json | 304 | dd2c9462a3a7645f8a3a58fc783eebaa040324db6dc52c25d40b437e3324ef75 |
| backend/eval/qa_holdout_e8.json | 1127 | 1db8c6f45da4f1553b7f20b7d42e28979698874b1f97eacb47f132fa0b251371 |
| backend/eval/qa_holdout_e9.evidence.json | 258 | db37477fc17f1ebd47bafa7ed64fc2ee8af94d00d64979c70dcd7c7ba65b2b4d |
| backend/eval/qa_holdout_e9.json | 1142 | e3a24bdc8c775b45c57afad1743a0224f114511dd76fbedf8550cc0e036e799d |
| backend/eval/qa_route.json | 126 | 7f782ba29a1c7421a5edebf1e7c169aee7f3bb0b7858df27a9736c4c0d852024 |
| backend/eval/qa_set.json | 55 | 5b3e1def51532406c1d88c4bb4dfce838dc6bcf408bf0c671fcb2e513c02ad9d |
| backend/eval/qa_tune_f.json | 42 | ea40f5257ba93d4561ac15fda831bbde6f3316a227dc6a3f352126b16c7a3caa |
| backend/eval/results.json | 1778 | 31bf73d6a8577b98c72bc2c6cc50f8170e43e59a8f8136ba598a75e743a3b903 |
| backend/eval/results.md | 79 | bfe505249fcb0b5c34748f30d8951aeb9e09c8c4cba9ebd2d2ce7542986ef13a |
| backend/eval/results_abstain_pool_base-fallback.json | 678 | 4bf6ec9c082b5131eaf09977600ff5739d114904c24601067574372bbdb3de25 |
| backend/eval/results_abstain_pool_base-fallback.md | 84 | 6012750a167fd530d2d6bf0ef9702a73a8e21a24b40d10b43bf0e032cfba8f92 |
| backend/eval/results_abstain_pool_base-write.json | 709 | 0004cc90ed512eaac4e60cb029b26b4074a66ec2604c74f2b64dacd28131bae8 |
| backend/eval/results_abstain_pool_base-write.md | 84 | e2aab90e25bf3b41abaf1ffbd6bd37c4d0d1d4ba391679a17daac729f9555e92 |
| backend/eval/results_abstain_pool_c.json | 709 | dfb4360e999f6ea58c615031d67beae92704f999d2affcba218e1053d372c4db |
| backend/eval/results_abstain_pool_c.md | 84 | 2cc3b29f57e7b67342c111a62bcb447a359d80174bfe20bd8d842ee743af18bd |
| backend/eval/results_abstain_pool_step2.json | 707 | 62f491ad880e2517ac163f842014584f60eb55324718ba41377eb6c694535c37 |
| backend/eval/results_abstain_pool_step2.md | 84 | e0563d8e664d32f10bf7766feca0074e2a0f466260ae81bd9b7eb68608dbd275 |
| backend/eval/results_abstain_pool_step3.json | 1046 | d5f586dd472418e05cff1755f3b768a6007a594720d6a0207fa72bae54d62611 |
| backend/eval/results_abstain_pool_step3.md | 84 | b1997decd0dcf4146ce10471d0e9589e7d806a17cf944488e6d1b16cca99010d |
| backend/eval/results_abstain_pool_step4.json | 1138 | f426fc59db93aa1dbff555313edd6d4f49eebd8ec0821759776a70c2683a86bb |
| backend/eval/results_abstain_pool_step4.md | 84 | ffda6040a2b8cad20a49692b4c4e6f0aaff11f8ef6b9b0bb97738e9c75730adc |
| backend/eval/results_abstain_pool_step4v.json | 1010 | b9d275a80a15bfa2873029c93a156816219c991af8473eead44d5b5b6f9bc461 |
| backend/eval/results_abstain_pool_step4v.md | 84 | 165dfee3cb95a11df65faea6e9016342a62eb77c4655a0878921845b89265e93 |
| backend/eval/results_abstain_pool_step5.json | 1815 | 943f201febc2677374b7f47192e243ec65afca9cf3277cc03cc1813eb2e450e5 |
| backend/eval/results_abstain_pool_step5.md | 108 | 40f5096b61372114e6bf803cab5914e940f5a311c7a04f4cda79c96987a158f5 |
| backend/eval/results_abstain_pool_v2-fallback.json | 672 | 8f7a712b8e10bdbaff6e296858529ff15e4e80e1cdf57fb2d54e84b9c8228d03 |
| backend/eval/results_abstain_pool_v2-fallback.md | 84 | 8aedfe5259490d53874709512a1ac2ec382490edefbdbb155bcf4b22738f8bec |
| backend/eval/results_base-fallback.json | 1259 | c3f02f6a6903ab2463292c86771a6a694f61a4e9fb6facc2dc6cb004ff206016 |
| backend/eval/results_base-fallback.md | 92 | d1f9ddf5a182813cd4d49c36d1b29d329b47d9d33b4a08c593ec15695db9caaf |
| backend/eval/results_base-write.json | 1340 | 398dff43e8defef144a2f93e22828c4e3d581996f3a253444a2dcce7bfae9618 |
| backend/eval/results_base-write.md | 92 | 46073ad78bde8cd5e461050f8313be52cf9dd21fdee9f5ae5ee8bb8f6a48d149 |
| backend/eval/results_c.json | 1340 | 444da94c6e7bbed9c105c302af37e26b69e7461885084606e38bb93d853ec296 |
| backend/eval/results_c.md | 92 | 70cb2161bc85b21412dae0f6249b268a8d8866f16ce519b67cef4e6dd7ce0f0c |
| backend/eval/results_holdout.json | 590 | b9342f9d1f0073f716ddf25272e24691fff05c6dab38ddfe69da732b7dcb8a9a |
| backend/eval/results_holdout.md | 52 | b7efdeb51deb288206a1e824956abf99ec3c2fadb18df6a4c489ee32826a3ca1 |
| backend/eval/results_holdout_b.json | 457 | c9c5d67a18b275752717a730f6036a1602c828b92066c9b677b16d3835a35785 |
| backend/eval/results_holdout_b.md | 48 | 181a8115b4119e5ab8aa811e592b924f5414df4e052a917f7b1ff51b5e60990c |
| backend/eval/results_holdout_b_base-fallback.json | 489 | 366ebffc51a62eefd90e5174b3c7ccadbefb878a755489f4c228ad378d3d99c5 |
| backend/eval/results_holdout_b_base-fallback.md | 62 | ab34ba2b040ecf32aa0803a6b341bb3bd5f83b6f94002b8dbea13f8a40a2081e |
| backend/eval/results_holdout_b_base-write.json | 551 | ebc33e539f8a011f973a3524234f10eceb09faf55e6f0bedb0a51e37fed36374 |
| backend/eval/results_holdout_b_base-write.md | 62 | 92768b84ffbec97f374f90a734125ae3857064e1e26f062670443012e4d7e297 |
| backend/eval/results_holdout_b_c.json | 550 | 6a4c8a91faa1ee0e9af7eaefb86d66aed54341a02af58641cb12a79adf6fef93 |
| backend/eval/results_holdout_b_c.md | 62 | 9cf485d21bd8f6f29da459cdaefea133d61d99d3253474dc2ad68601437a8c9c |
| backend/eval/results_holdout_b_step2.json | 550 | 04d445a3cbf33e2a2e99e549ffadf7ce3b0aadf6a08ad610e1df48eb851735a9 |
| backend/eval/results_holdout_b_step2.md | 62 | b4073fd36286219209422dee8316f3e6d09d945cd8766db75a7b012b19aa89ee |
| backend/eval/results_holdout_b_step3.json | 677 | 53989c7ebefe3a813a8fdc89850c4f0a3e61b22e2cf25fee83dc37d33d38825a |
| backend/eval/results_holdout_b_step3.md | 62 | 4d101d517a5b86df6b7e23e19acbe3080c204d5336cc2c5cbc16599f32fff8bc |
| backend/eval/results_holdout_b_step4.json | 769 | 07da27f5ac133907e3defcb3a6db68372538798a7f19189a1db4efd1378bccbf |
| backend/eval/results_holdout_b_step4.md | 62 | ba9a75d7b135cd4f88aa545ba3cc3ec6e1a9fe5535669d1ff33db9f532ca4aef |
| backend/eval/results_holdout_b_step4v.json | 723 | 517884111ffff31277b32c10217a244575c42f4618511cda17c0273077fc1ada |
| backend/eval/results_holdout_b_step4v.md | 62 | 335a1fb68d9bffd89d2ec80a4708795308dcb8116b199ecb04ffc877061940f3 |
| backend/eval/results_holdout_b_step5.json | 1094 | 48e3b7f7b62791e8b9c7ab61019de64b0c7bdc5d9ddfa8445ff06f42f6ea2ce1 |
| backend/eval/results_holdout_b_step5.md | 70 | 20e3117b4b277a37f3f96f4a8f9997c93ad192d5f206d7733a32144243316aee |
| backend/eval/results_holdout_b_v2-fallback.json | 491 | 936905e68d0143542264831179096a70aaa4c424704b5f4954bac0613450d7bd |
| backend/eval/results_holdout_b_v2-fallback.md | 62 | 800f3938b587725947fe7e37df0a2b2060935a95de3b66af87cfb617e7c07ba7 |
| backend/eval/results_holdout_b_v3-fallback.json | 542 | c4c3d0119758a961765984713b6aabf48f15b8ab172b887de95c673e180efae2 |
| backend/eval/results_holdout_b_v3-fallback.md | 70 | 6d544781387da61a41b628144bc7f1480f31ce2dfe20266941708cc12d35a286 |
| backend/eval/results_holdout_base-fallback.json | 628 | 3b84a867347d273e76afb69481b439bd4f290214b393f8bb5143bb880144a8cd |
| backend/eval/results_holdout_base-fallback.md | 66 | bdd404b35949264d40d7671fca863110d02d6e93d20007b12245790eb6efbffc |
| backend/eval/results_holdout_base-write.json | 749 | 04f5feada3919e6e3047c6c29c83c5d1b1a302b04ce9dc008138a075cff34d38 |
| backend/eval/results_holdout_base-write.md | 66 | aad5d2de9c4b2892880e3fed7cdd89e64d14ce172f76838993b73058553946bd |
| backend/eval/results_holdout_c.json | 748 | 8f3793e618e87891ff268c488c5ccbe34e62674c24c1eab80b750159ea229a17 |
| backend/eval/results_holdout_c.md | 66 | 257fbec7331ed8c2778b6ce581e8ab4dbc3afd04ece97b510e88ebe2fae98c02 |
| backend/eval/results_holdout_c_base-fallback.json | 655 | b537f46b7f2de64272afcb53be0931c96b31196f821dbdb7499acc6308a36033 |
| backend/eval/results_holdout_c_base-fallback.md | 69 | 6e34dd35345131070fc4d237ef2d21dab494c7c15caee8af03d3bc9c8dea41ff |
| backend/eval/results_holdout_c_base-write.json | 700 | 94a75e051d611610504ebcf3ba625ca3fa90e57cd6af74528b45e4b8837b0ceb |
| backend/eval/results_holdout_c_base-write.md | 69 | 52be3b0626091f48bebaad4697dc6d5e5a3ae6ea859df5b818c84564b8944f9f |
| backend/eval/results_holdout_c_c.json | 700 | db36e7dfedb01177f617c53882fe27943dc2890be70ba30673185c8f7c031c2f |
| backend/eval/results_holdout_c_c.md | 69 | 6ff9c5594617f4a61611d974c404d6cfebb6392e0b141505a3ba03087949fae5 |
| backend/eval/results_holdout_c_hybrid.json | 913 | 15eb23063e4cc9c6cbd0f635ec82f3e98da915ffea8ea0c69a3f4732503856be |
| backend/eval/results_holdout_c_hybrid.md | 56 | 67697b59d94106aec4e24d26654f4afbd3f75e3964732cc7054496dff28bf5d7 |
| backend/eval/results_holdout_c_step2.json | 700 | 1c4a37b5b3e6f140f5f289077ee65a1674e54e15a5a9897040ee43f27dc57498 |
| backend/eval/results_holdout_c_step2.md | 69 | 622ebbae7461e1e5065edb4e2b61cd7f76c902f9750759ed1d260e29eb42d24a |
| backend/eval/results_holdout_c_step3.json | 860 | 4c66f0e9beed427dc4b0b06f9a1e54973c61209ebb0bb294bc2aaa605776a832 |
| backend/eval/results_holdout_c_step3.md | 69 | 739d8d107e5e8b36e760f349aedb5f67e34c714b74f3540390c1c013ea9d8ad7 |
| backend/eval/results_holdout_c_step4.json | 986 | 82a5b551e437eacf33c03d9d05b75924a800589ba1edd7d76ae65a37845cc835 |
| backend/eval/results_holdout_c_step4.md | 69 | fb55f0d5903d6e8076af2f5963176f81f3bde3641ddbf7b7f3bf1bc2040b879c |
| backend/eval/results_holdout_c_step4v.json | 895 | 8067969c4cb662e6633b31a645b623f6cfc96957ee1fe558cd785e68e63cfd69 |
| backend/eval/results_holdout_c_step4v.md | 69 | e315708f6752300d0821d1ea5dd1365b4e75734e3242f0898ff55b82c3a16f85 |
| backend/eval/results_holdout_c_step5.json | 1387 | abf75abd10b5485e055516439874535fcfcbe7fe38ea0e26bac1cb72fc00512a |
| backend/eval/results_holdout_c_step5.md | 77 | abc11acf607e1b1c03087fe6e9a6d5e484c3764387a68b7bd17c9b24fbf746c5 |
| backend/eval/results_holdout_c_v2-fallback.json | 667 | f6ab6d5b96095c9f703439265a4b4c67e0af32844957dd7fdd40b20cad73bae6 |
| backend/eval/results_holdout_c_v2-fallback.md | 69 | e7595fbbee410af0d3ad55568a9832be410506e5383e97950b33589945cacd74 |
| backend/eval/results_holdout_c_write-route-hybrid.json | 961 | 0a269444a63acd805ff995ef0c0d91d2a017b4f9337b285497afd580d9d6f510 |
| backend/eval/results_holdout_c_write-route-hybrid.md | 56 | 10a4cb58ec60a7082b357fe3b77ca32ec3695919b47a0d6a38c1ecd58c29e35e |
| backend/eval/results_holdout_c_write-route.json | 960 | 51313b9778e57822d2a3fa1c1c5403818d0f3d66bc242ee5e4c1ad3bcd383fb0 |
| backend/eval/results_holdout_c_write-route.md | 56 | d5862973ba53254f7ca23d21cb0fedb7d27334817c9432b5fb549f762d260cfe |
| backend/eval/results_holdout_c_write.json | 960 | 9c3720fd385c9802042c5fbfbe159e8a17d5aa978d41b979ead793fa723ffe34 |
| backend/eval/results_holdout_c_write.md | 56 | 14fd2f60208dfe26a04c3bd44bce2131300081e37f728c4c3072b65b51b4a2e2 |
| backend/eval/results_holdout_d.json | 715 | 27530f9e6f96c84739613eb992b3754431f66f89c216a255d1acbe1b3d3015ec |
| backend/eval/results_holdout_d.md | 51 | e95482910752b3ac313d12110fe0700f4cadcfa78d1ff1cd6b2a78bc9a4eba4d |
| backend/eval/results_holdout_d_base-fallback.json | 508 | d5ef05ce2026aec3d077dfca794549c74ce293b74e500ecf4040f06c7c283f14 |
| backend/eval/results_holdout_d_base-fallback.md | 64 | 7678afca02c8c95a8b37d3ad134adb44597302811650280ab3b3674583bf7666 |
| backend/eval/results_holdout_d_base-write.json | 584 | 05481cf1a56c54d5fd4067597302e3dabfa5b323cd7319b320b71f797dd0a464 |
| backend/eval/results_holdout_d_base-write.md | 64 | ed31a919205f2f52d7a40bbeb8baf25518567edf0b36d24519dc25a4a4dbec15 |
| backend/eval/results_holdout_d_c.json | 583 | a8e947e293ce1697dcaa31e0af50503ebba3e998915d5b352be67b9f5a755b6b |
| backend/eval/results_holdout_d_c.md | 64 | 9bae57a49bb94bf0a6df9414ac8d33f65c9a7fa02202af25c115fe5191a0132e |
| backend/eval/results_holdout_d_hybrid.json | 715 | d840264b8ae44b75ce0fab75734347660f6f7408c98748a6fdb4f90b6e5a962b |
| backend/eval/results_holdout_d_hybrid.md | 51 | 9a4faa280596a14371acf9d7e8d578412956b48cc372bf0acc8576efd438e7b9 |
| backend/eval/results_holdout_d_step2.json | 583 | 4c7a9a87b8a220d64312b720ff2120d611bd9a0d5aff62b0baec7801e0f0f770 |
| backend/eval/results_holdout_d_step2.md | 64 | 5a99789dd2c3618bcd6d09b23dd5c55264626e36826d9787efdd4d4e7c145e38 |
| backend/eval/results_holdout_d_step3.json | 743 | 3917d63d3215af544ca2e8c883448c5a312bfc5c8f42c2abc17a8f0d4270f69c |
| backend/eval/results_holdout_d_step3.md | 64 | d610e77a4f52f785c5333c61fa4caea139202b565ca5233401306ef6d43e6c6c |
| backend/eval/results_holdout_d_step4.json | 865 | 394c29821c8df36f4cd8fefb5e816f0b6089bb93941468123740d0ba281e7d08 |
| backend/eval/results_holdout_d_step4.md | 64 | 4b88f278910d99d348a1c50d1a68c7ee02c37bd7c37bf2962715ce9a80258537 |
| backend/eval/results_holdout_d_step4v.json | 818 | 50d0e1eb1bab0e0a901f2cebb7dbc4f69d08c5d3eb134ec7f38c58b6984407bd |
| backend/eval/results_holdout_d_step4v.md | 64 | 57191e2b0fd7b0a8eebab4531e923a775ab943c8f35a17bc9d425987d1d304b4 |
| backend/eval/results_holdout_d_step5.json | 1211 | d6b19ad2f2ae9b4c89078e08f9cb6bcb1f6bcb2b646c73ca99ed38c1a28ae5f2 |
| backend/eval/results_holdout_d_step5.md | 72 | 0ea5a4748b084101957c5b276243ee2b4540bc27dc929526251a876850675f95 |
| backend/eval/results_holdout_d_v2-fallback.json | 518 | e26fcf23c80a36469d34f2e826dca2d02421bce75706de0fc051ac3bf0ffd514 |
| backend/eval/results_holdout_d_v2-fallback.md | 64 | c097d8298227da604ee9f7004f24a495838a94c43cd29bf2b45381e922f30741 |
| backend/eval/results_holdout_d_write-route-hybrid.json | 791 | b1ed77be3aa7fab1c16d4de46d3045e8e5576dc363af4325827e6b7dd159aed8 |
| backend/eval/results_holdout_d_write-route-hybrid.md | 51 | 8976830dd9598cdc8bfecc275089a108c8d4ea865117fe7a26699687ccc75561 |
| backend/eval/results_holdout_d_write-route.json | 791 | f607ac80d06b45532f64f4611084baecf0066cc10263441bea558ba0713475be |
| backend/eval/results_holdout_d_write-route.md | 51 | fcc56d8cb964833e37f4e1c1a9d7413a1bd156b9a619ac15cee4b76cdcd3d2d2 |
| backend/eval/results_holdout_d_write.json | 791 | fe4d86c6433262cde73f46eab4109cedc39e876c665d19ad6173cc8d1fa2e98f |
| backend/eval/results_holdout_d_write.md | 51 | 0cb751150ec35738fc810f24bcb16133f637622c8922a9fd69cc9900eced8f64 |
| backend/eval/results_holdout_e2_step5.json | 5080 | db032591565ec935043ba723db67c16c35f7e6ab54d8d998edbaefb609a1117a |
| backend/eval/results_holdout_e2_step5.md | 152 | d2e55bc49518f8d97c1f956ffac6d2c5e65c150f3f907ac24d06cf13e9f78d42 |
| backend/eval/results_holdout_e2_v3-fallback.json | 2266 | 8278c221243a426ac46d4988ba36b4feb9286cadcee3243a1f3a9d11cfcf61ff |
| backend/eval/results_holdout_e2_v3-fallback.md | 146 | 020d6d5643f6921f3cdc6675bd4281816947d85a8bb9096b66fb2e6cc3f3ccfd |
| backend/eval/results_holdout_e3_step6.json | 5117 | 751dafcfcb900850dd7030d79996a26bafef8362fa3e91bdd80b872ab21b42f1 |
| backend/eval/results_holdout_e3_step6.md | 152 | 123d9cc87da6a8f577b6eedef93c705bc7aa10ade38dce642b7ec0eebd0567d3 |
| backend/eval/results_holdout_e3_step7.json | 5108 | 1342f6df39acd672a5a22176515e22fc7f06068f7244e542db9e45aee6660c7b |
| backend/eval/results_holdout_e3_step7.md | 152 | 8e789d84048379bcc61a809442e38d04265d8a531433fb5022885280685e3cfa |
| backend/eval/results_holdout_e4_step7.json | 5066 | 556bd729620a2ecdce76930ed46303b67300ca5ec9425f69ad2dfefd16d1f408 |
| backend/eval/results_holdout_e4_step7.md | 152 | 894e3e1929738df67330a60222c4e67b5f5077b7aa427f01c7efeff3328bc040 |
| backend/eval/results_holdout_e4_step8.json | 5171 | 05e46e617f982b1f206b534066ececdb0e93ee42eb99db2c5eed1b3d705931e5 |
| backend/eval/results_holdout_e4_step8.md | 156 | fc4ce9f41201a3f080a8271099e840295e6b5a95cd2cffcc3a84254fbf60c193 |
| backend/eval/results_holdout_e5_step8.json | 5201 | 269b8812263653d16f4931a73059ebf0fab342729133dabe468eef255140f208 |
| backend/eval/results_holdout_e5_step8.md | 156 | 32e19d178dc49a64b042b7fecc44610b299d6543c4a6cf41c44f4e7e86e1db06 |
| backend/eval/results_holdout_e5_step9.json | 5199 | 7f016ebc3edde36a17110e1d1eede09764bc2c5801e48834086af71adfcef72c |
| backend/eval/results_holdout_e5_step9.md | 156 | 5ee03f1c00e6046ebba40f0c33261d541a7d154a9f5aac950c5952ac685b7bc9 |
| backend/eval/results_holdout_e6_step9.json | 5110 | e42916a7f4281fc3ec6232754d4a54d6bec8e0aaf16655214ccbe613e1fa9c74 |
| backend/eval/results_holdout_e6_step9.md | 156 | e656662ca47b038db42e6a33dfedcfe9f8930229fa93a7c20c459cade1f63019 |
| backend/eval/results_holdout_e_step5.json | 5196 | c16f8b256a7fd59aeb8014865a73f6ecba0d93d9d72c316a8d08e49a0e634d10 |
| backend/eval/results_holdout_e_step5.md | 152 | 40407661270d12dbf0f117b9c8f7252fcd0fe3a20be83d86d05c6e5dce147be2 |
| backend/eval/results_holdout_step2.json | 746 | 88efa310032c46293d5bc28065f0c3c9d0cf830e17fb8b81d7f1ea3319f9af41 |
| backend/eval/results_holdout_step2.md | 66 | dbbe076cc84d3b31bbe91f9751909c0477e0908a3358a9d315705bb54a81f968 |
| backend/eval/results_holdout_step3.json | 893 | 191f6a3370239e3e801a09c0ca7382253cb09ee6405d86f0a6d3c39ac1f6747b |
| backend/eval/results_holdout_step3.md | 66 | 95c84cb9751c18d20bacaacc05c28f47eefc67c32fa08dc3f56579d2ae577f1e |
| backend/eval/results_holdout_step4.json | 1011 | c71f2016930067339cc25160ab25c2bc0d521227b7129b6b5f461f003fd6f938 |
| backend/eval/results_holdout_step4.md | 66 | 0c9e3d64da939babcb67ec0fa49fdeb17b20759c34d131cb29962fc020318540 |
| backend/eval/results_holdout_step4v.json | 1011 | 4349f0aa681f0e98fa184ada06d1752f7159778a39e7e350f05194f1d378a300 |
| backend/eval/results_holdout_step4v.md | 66 | 8f998ef2aa439209a3c823eda759854e1e4b6d128fc90c632e851a7deabbbaca |
| backend/eval/results_holdout_step5.json | 1381 | ca5180289f6cd2cb0fc8a917dc52245b99e663b064e8f8ddd2d5f368bac58b2e |
| backend/eval/results_holdout_step5.md | 74 | fe5559f728e748d6af434e35a5ae2f6933c312efb94b023a480e3726bdbff085 |
| backend/eval/results_holdout_v2-fallback.json | 638 | efeb205e681da3b6b451778a5fa0fcaea1b5e763770f017ac10131ed451f057a |
| backend/eval/results_holdout_v2-fallback.md | 66 | ed9adc9e8863d29cc3ad874531e998a4680be51757268cd70d8c8bd0d0fa8d53 |
| backend/eval/results_hybrid.json | 1778 | deb92902c7646bd6c06a4edeb7728c99e9dab460af383c7cc609ccb25a339509 |
| backend/eval/results_hybrid.md | 79 | e4b2d5fbf84e3ede346b5f96d291996435c84e4d896c7e6ba65600841334e3ec |
| backend/eval/results_step2.json | 1341 | 92eac99d45629f8d9a15caa626ccee7a596bf4ee26cf993598233b1d06ce7413 |
| backend/eval/results_step2.md | 92 | 1790f0b940f579ccee02f544caf058c2fff99fb98419990f827640bea6093b94 |
| backend/eval/results_step3.json | 1579 | 0c6cf928c4b4a96c9774122b7b7a33726910095b58eba203efe6749f9b5b7478 |
| backend/eval/results_step3.md | 92 | b110b8d3897bb8d773f4eba564743a168f7d9ab43d705bd367e321f5d1d27b8d |
| backend/eval/results_step4.json | 1671 | 9afb6943b932db190fec92f19e91fdb03d75ba4ff2d1042d4c171d9a8fef36ab |
| backend/eval/results_step4.md | 92 | 852d1c59b8ab34e4b580c6ef7d98789db2a8a2069c4acca0ff125d036eb9a712 |
| backend/eval/results_step4v.json | 1653 | 068bbe346bd040ecbf818b32a4d9767747ae9febb895a8e452efc5846d13fca2 |
| backend/eval/results_step4v.md | 92 | 4d5d804622313cf135417ce1e5bae783db8209fff43dc63b2aa155e5618ba6d2 |
| backend/eval/results_step5.json | 2462 | a5f21fc6dc72b64ae55d0f03556b219681d6df0b66bde7de687843d788e5fbe9 |
| backend/eval/results_step5.md | 100 | 527c31cb0d39b5260baf07d7c0490f24647d29c0ec97d76fa5e00516b7940772 |
| backend/eval/results_tune_f_base-fallback.json | 734 | 0724234d886a233bb92248cce333ca546554fb80949f477608aadb7128f0609e |
| backend/eval/results_tune_f_base-fallback.md | 79 | 027304971c38d2246968fc23b2acadb632d11aff4e1161de780cb230c9c6d756 |
| backend/eval/results_tune_f_base-write.json | 813 | 15b072ee753a28134335a092b586999d609fdd07f95d557fae339dbdd0c4c82c |
| backend/eval/results_tune_f_base-write.md | 79 | fb09b141dd386e752a677af35e5fb9e5c7ce09d9149acead3798fe5a6dc48ef3 |
| backend/eval/results_tune_f_c.json | 814 | 1cf4df76571d0efb3d72f6cd40e61d5b92654fea7d95e83102ade1e7a2e845e2 |
| backend/eval/results_tune_f_c.md | 79 | fd321771cf067e4c926459307996e01341f3caaca28c856bdc0465669d7abd7f |
| backend/eval/results_tune_f_step2.json | 811 | aecc7222220bc7c662aab247535b9bb1c95d984518e4da74ec177493903ea86f |
| backend/eval/results_tune_f_step2.md | 79 | c14f562db3e83dc6e98d5cb44ecb96b5a92634d81525f40d5ae2c3be3db7c16d |
| backend/eval/results_tune_f_step3.json | 1099 | f9b6d29811ab3de1b5a46720f5cafc96c266db9d175aadedde168d39f7ac6185 |
| backend/eval/results_tune_f_step3.md | 79 | 2567bf35a0d23cce73dce947f74e4101ba5a3bb737d054464c237bbf7157d496 |
| backend/eval/results_tune_f_step4.json | 1384 | 2d52e427e7cdae6905745a06028ef6fcd9da8cd52b78dbd5ea82707e0761b95c |
| backend/eval/results_tune_f_step4.md | 79 | 18d237755060878dd409492b9512872d676a38cf09319b5d6c4f4dc053965181 |
| backend/eval/results_tune_f_step4v.json | 1112 | f94711e1dbf51b5ef8073045f2f8f201d51e15c6696acf8d498c2e9e7aa51317 |
| backend/eval/results_tune_f_step4v.md | 79 | 9d312fa1705d0b0618f90f1890a5000fbb5b63e9dbbd473cce608fc47a06a1e8 |
| backend/eval/results_tune_f_step5.json | 1952 | d7483db3b9a244378e821a6949c85f459cc8947a76e780a428a6a17f83d72a58 |
| backend/eval/results_tune_f_step5.md | 87 | 9b45cee5a31d6f553170909ceb42b6bb7be36b5f9c86ba176797c6a8c2f8d5f7 |
| backend/eval/results_tune_f_v2-fallback.json | 720 | d435655b18d9a29f0b1306d09da76c7f7777c633aad383349c5874bb7916999d |
| backend/eval/results_tune_f_v2-fallback.md | 79 | 884c5cae752d663e203309a8afdbcd0f5af324854b87ac46c20e31a2d10e832f |
| backend/eval/results_v2-fallback.json | 1259 | d06ab58666a25cb3b6686464908177eb97eb3d28ec565442d495c93eef24b3b3 |
| backend/eval/results_v2-fallback.md | 92 | 09ce13a0c14ac9cdd27f8ef84de16df9f1cb66ef6380718d6eeb076f1c968c41 |
| backend/eval/results_write-route-hybrid.json | 1863 | b50e378a952cda94eb5d06ad4cc6a9ebaa2d681859ec8cdfc371411fe3057b74 |
| backend/eval/results_write-route-hybrid.md | 79 | 5962de653afea85ac30e5816e029b8cef9b445d5fa86537b0b5c786fc3eb5a4e |
| backend/eval/results_write-route.json | 1861 | 555aea908625468bada37f9fe5c03e35cfb68114f977b88c3adfcf31142a4c05 |
| backend/eval/results_write-route.md | 79 | 44d92d01250995394d3268ab367057b400feb49255b71bd2f7a375af2503c9b3 |
| backend/eval/results_write.json | 1863 | 3311995be41d5f795e6bbd1b14f81aa0069426fe3b7d3c3b38560f5f4a69da62 |
| backend/eval/results_write.md | 79 | eab0ff2ba8d884cd020380c495dd59ecc0ebfac20a58b72f657e715646f5e213 |
| backend/eval/retrieval_eval.py | 82 | 6e67c4ed26fa73c6e9a2f35e6031bdc82d698013bea9b165751c09fb54929b1a |
| backend/eval/route_eval.py | 240 | 9008af25970c0f9a4d5ec6643b26c6abff4b1b6b02d5b211e24c3436614e8daa |
| backend/eval/run_eval.py | 786 | 6ca5e74cccfd8627eaad3f5c26bf8bbc205510afdd9232218113e4836ea191b6 |
| backend/eval/validate_set.py | 167 | e9622ae319b846905b68d15acf09dcb918a2b0e446de13e6a5fac280095f8c5c |
| backend/llm/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/llm/adapter.py | 184 | a0dabdf92dc1ba5dfbf5b19173dba5aeefc4f6905410d7d3a6f2c79b90940fc1 |
| backend/llm/claude_cli.py | 149 | cd4f579fc04aa109caa73441d15010906b416013324341f20755216e95521721 |
| backend/llm/claude_client.py | 458 | a407c6375f6c235437a35b6cdf8857898dbb295b89cb05033ea2efda9c067f6e |
| backend/llm/client.py | 227 | cf02c34f93455bc2c89162ffff2366cf9bc27f594efa1332e10c33f91d18f127 |
| backend/llm/deadline.py | 47 | 0718240286384146ef95b9f81c655818325bc08d247a0f546ca00122074d4daa |
| backend/llm/external.py | 77 | 21a34f29ed536b67c70c823137d1cc1f71101e09f40bec355dbd520406e84b27 |
| backend/llm/jobs.py | 368 | 622ab0ec95744e9d949ea71e375a92fe2a4695e003ece1a73da07fd993193e2d |
| backend/llm/numbers.py | 212 | 8fa152a13d386440942943a0315d349ecd83e8b8cc3ba64f7abf26f1b4baa31c |
| backend/llm/prompts.py | 233 | 28e9d24872a2b7a4e220991076c22759ee0c0b2364f7812fc113313e2ff0b197 |
| backend/llm/route_examples.json | 280 | eb09105cba78bdfdf08215fb4b3363b16530027eb04a8df4c754c961e2b1681e |
| backend/llm/schemas.py | 91 | 821bddc0370c34a6d4f7db2a7dba4efd4cc80944a20199f1e9148bc386b5cc6f |
| backend/llm/think.py | 84 | 27703fe5b1295fa1199a6e0d316166cdda60594afd1d9895b548ab1c628fde12 |
| backend/rag/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/rag/chunker.py | 134 | e0a7ab7d0073813a77f6b5c840913aa8c0150afb3393a6d43a97c9b73f9de65f |
| backend/rag/dense.py | 103 | 6d8e8144978c1da4d7870cefa6f7bb5b7584e2f03971bcb7cd893d8e9bd291bf |
| backend/rag/doc_view.py | 95 | 1dbfab27d20735bfada8bcfc4408035e1a5a417d9fe6ab197e706c0bb87d9afb |
| backend/rag/embed.py | 56 | c91f6ec4b04bc57009e609fcf687ce3bb29c3110f68ad2c0b03e11fba535c8d4 |
| backend/rag/sanitize.py | 164 | 5b88f1d0725adbb611d5b132488a3ccd8dabd72b6951cdf6f789640c58beed5f |
| backend/rag/search.py | 107 | cecad2d5d36fa1a07ee858569bd196e2a38ee9a884ba3cca0f60ff799897b575 |
| backend/rag/vector_store.py | 111 | a951ed3be41b940f7f44a78128e69cb6ac20d9ae9e423b73d0090733034a6918 |
| backend/repositories/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/repositories/csv_repo.py | 45 | ac3821fe0af2c9f146d9d8692a7bfa418a8e8c84bcff51aa279e377608c2e6e2 |
| backend/safety/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/safety/templates.py | 142 | 0b4f6eba91207fbede9b8676dacc188a789d01d96b9f2f83880fb974bf1e3ec6 |
| backend/schemas/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/services/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/services/answer.py | 3322 | 2472fb9fa7c7c0e3bfd0828dd906ac0ef31cba794b8ee893082c832d011598f4 |
| backend/services/answer_store.py | 60 | 571e2883326792f97db8b3b6d3b09a39d06982538b26d04edffb2b5f7160302c |
| backend/services/blocks_v2.py | 113 | 377b83431d66a5f221151a20443c92d58627db3bb0e9c720fff1a6fbf41f05e6 |
| backend/services/briefing.py | 266 | b82d4da4f28c116107de1048df0e241686988e89128585a97c365834149e0d2c |
| backend/services/cite.py | 36 | 88ab601117c529f758f9c2a55f82751b5081dd00bdd63133132c4b8f89fe8226 |
| backend/services/followup_v2.py | 866 | 5a9a6ab2aaf56f6cc85564ebc0bd8b5b4267f4aea85b8abc1ad3bb8105cda584 |
| backend/services/guide_card.py | 158 | 37008792dd1cd7786e9d5d28bd1c61216d14ce8a72c9c642bd40ca113afa9ae6 |
| backend/services/metrics.py | 127 | 5c0c28198afe48c8c2466d032c632d2d4d013e4ecb2eea737c02171f284c550b |
| backend/services/notifications.py | 350 | 764ba4f8a33c701f40980e4d3db4b45a61289d315d75427559b8abc90846ccee |
| backend/services/repeat_alarm.py | 44 | fd9fa67fa659ef334b8fd9cb16006f08a1679ca7012855c2733ffae67a8700bd |
| backend/services/report_rank.py | 70 | 0d69ab4829cf2d3e1722174c8140b7d29dcee3a7af3291bba3cdb54102d77a75 |
| backend/services/revisions.py | 84 | a12cbc28c8d8a1f88951722db36457f84872dac0966864dffdb2bb1bba1d7137 |
| backend/services/routing.py | 128 | 22fa1a738d1bdbbed56d246b46d983a79a9ecca30eacf50340a112fd2a7a1af4 |
| backend/services/shift_reports.py | 70 | e6f43e5512b12fd7ba0410d323f3aa0f85e274a222b34bcee39ac19c28d68fe3 |
| backend/services/shifts.py | 83 | b68e27ce379a05549d5a52d61d0c62698953b0b83ec48aabbc6eb2df8d8895c5 |
| backend/services/steplog.py | 228 | 7b19f868a6e9cdd35ca0fb9135e9389144039f903a2d4ff7f23d5c1b6614abf0 |
| backend/tests/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/tests/conftest.py | 59 | 0d1c48427735153a663772fa8529f621a5364f6e349011d57cdec53a7f369735 |
| backend/tests/req_map.json | 114 | 0a9a60e4c1e2813e65d60b8f987439d99d95d583f9bbb2be2873afb0f2a1005e |
| backend/tests/snapshots/fallback_answers.json | 12170 | 4e16dc7c696118632bec5be4e36b47e579cbe389a66521630b704e2877ed749c |
| backend/tests/snapshots/write_rules_v17_cases.json | 294 | 1c5868fea4eff8309c5bd3ad86c974b5ce9a5857102f72bec9de90030306a9de |
| backend/tests/test_answer_fixes.py | 99 | 5e7aeb924e55e00ca6906911537a615ed8253ef1bd818ac337dc213053cdad1d |
| backend/tests/test_answer_gate_v17.py | 98 | 0532a26ebe4314f3485901a56fbb9f49d634b3b2b48d35d652614461f7d25b60 |
| backend/tests/test_api_fields.py | 91 | f71c583c593210759d96cc33c76cbb74d7b635c9680bb0140c99d620855d55f6 |
| backend/tests/test_assistant.py | 246 | 087e7093ed3a9574b8000f96e1c65293a9ede00bb22e39f104e3b78de33cd0b6 |
| backend/tests/test_boundaries.py | 146 | 1b78c0fa37eea82d019dc3c201443e69bf5725de285f74be89d175a29a344448 |
| backend/tests/test_briefing.py | 321 | 9976cf89b7d2d83c163ae1fe14c7a7e925348eed303dd717950052cb5d09f170 |
| backend/tests/test_bundle_a.py | 223 | af57077f2ffefa21eb6621b6c419eb1474a4824c44c978ffa59808510bb54cde |
| backend/tests/test_claude_cli.py | 345 | 5bd47b5cad73021566568b65c060b4af96e0249052635a10d6500feb138998c7 |
| backend/tests/test_claude_client.py | 294 | 478c73c7ec67b9692e1f12483fa402a5ee5bb8d9ca9b69121f9fe455b62475af |
| backend/tests/test_core.py | 118 | 3e99059a1e7e6812271cd8619601812547a313ae91b14430adde6343e98c8a4d |
| backend/tests/test_dense.py | 105 | 5e04b378f8c468f82d6af9f806d17347d0e24d5b1621d11696b91c409144024a |
| backend/tests/test_doc_write.py | 326 | c00621687075b2bd3f8c00d0ed215285fe3f52f7990aef0326a864967b28266d |
| backend/tests/test_errors.py | 94 | 53d527a47cde12cf16e0c2062ea70e5689eb76fffa6ef1308654f3e0cc1134cd |
| backend/tests/test_eval_tools.py | 337 | 12a379f86b17db39cc5be450d731b6484736b8c4ac8df51bab5f214a8fca9325 |
| backend/tests/test_external_switch.py | 239 | a10ff0550f37fb729d2c067074b1140bd79a5bc54e2c811c61235eb84ec29997 |
| backend/tests/test_fallback_snapshot.py | 61 | 30b7ddfc0f2383618b503b63b436f7116e696a89b6bd80a00b098916c2b63813 |
| backend/tests/test_followup.py | 243 | a049ea9c18b1bb4af119de9dabb626e38b1be7ebf6a5258ea647eb4884fc6fef |
| backend/tests/test_haas_names.py | 218 | ba797f28b6585c970e97dfdf606101d8e13fc90b076d9a3a8ede2eaefb9755ed |
| backend/tests/test_keepaway_warning_v16.py | 154 | 1c6939374971585975d73e4f34d117b89fc1d88320ea4ec92ed5ed8558d3d983 |
| backend/tests/test_llm.py | 196 | 7c89bee1aad51c71178bd78c55067bbbb42679e39e39816b4caca9646460216b |
| backend/tests/test_llm_contract.py | 52 | cccc76ef79c906f3e44baee8dadb3a7f36491b8654d6ede15bb7c5b89d000e62 |
| backend/tests/test_llm_guard.py | 69 | a257710dcad32f54f8c47e6fc0b6e5880144ebbd09d9bdc71ca8f4b3ad0669fa |
| backend/tests/test_llm_transport.py | 63 | 62d1083e7b5e72a555f3b39e36285eb6cdcde9e964ecec42d75157541ad0c91a |
| backend/tests/test_numbers.py | 133 | c40fd87813521a0022b381555ea66de6a2dd88f5a530e7368f11d5c46da09758 |
| backend/tests/test_numlike_grammar.py | 34 | e81b048046e647017a97d4380b28ae63c01ed73797ce1b1263bb8db7deadafc8 |
| backend/tests/test_parse_v10.py | 291 | 1302ac7326380bad8b1db574495e3559bc647f721fa13013c90edbdaad12be83 |
| backend/tests/test_parse_v3.py | 244 | 575f95ce6a3d824b1cd647babc8455c727e97d9f456d156dce42456b8d0ff52b |
| backend/tests/test_parse_v4.py | 334 | 94f15aace1db20ddce872d953fd89c6c8f7b966b807586a7957d4dc1930779ec |
| backend/tests/test_parse_v5.py | 305 | 23cbf2aa960de989567a6ff7615d53f04263dabf3f7fd28a32138d83f42a3b8e |
| backend/tests/test_parse_v6.py | 144 | fbbcfce9fe833a2a2ee11777f9a6c85c2724cbb4ee70e6a0300e43152c764f4a |
| backend/tests/test_parse_v7.py | 96 | 667103088860e5358e99e639dbcfca7ed9d99469e3fc70c5f60f2faa14f8153a |
| backend/tests/test_parse_v8.py | 356 | 2ae90b5b6df6a88f48dc62cc8dd011552626c51c14178933aebd6625d8f320e9 |
| backend/tests/test_parse_v9.py | 507 | eef6afe2523967f91f8ec21fb63d4dc140e273ea6d2e5c379f65a8a2b7f81393 |
| backend/tests/test_req_map.py | 64 | 60abd697dba9a734d64bbc46b4825d3f15dcad437782d9825a58cf0379ee17b5 |
| backend/tests/test_routing.py | 182 | 0a0b5a590743aadd8cb6404e9e64ead0db6186818e0fb3002ef3bc9f3afb7478 |
| backend/tests/test_run_blind_sb.py | 48 | fecbda6e1779c4de37ded51a2adb621431e8fd5f759b67681f23c3670a462517 |
| backend/tests/test_safe_write_v15.py | 204 | 7859be10002cca3298f6a1167764dfd2af89377005cd4e95ae2315ce9d6f10f6 |
| backend/tests/test_step_log.py | 626 | 2ef0af87262c8922acd739b108d40f57f7d32eb1cdd9778a73ff4c03ecb6802e |
| backend/tests/test_table_fill_v18.py | 162 | e0180e5a0b5120ff9f5ab78909dec03037ee894e9830deaf57b19923be55e884 |
| backend/tests/test_think_switch.py | 239 | 308d4433d2755a5879c18107c25f83e019c8bcc0c5fc25ca7ae481ea4432a174 |
| backend/tests/test_tiered_gate.py | 135 | fd81c1d8dc1351cc0861919d148788a26e9556da2916aedc652c704999f4816e |
| backend/tests/test_value_echo_v14.py | 59 | 5d30a2713fb97118633ca285310242bc9a2299df7c17cb8cbaef452458a882fa |
| backend/tests/test_write_prompt_cmp.py | 69 | 47be61e7718cf70fb3b1324a8e741382bc434b4c30fcd6128d9185a5ac347314 |
| backend/tests/test_write_rules_v17.py | 135 | 7ea4e55954d67038954e0905e4b1626c1f9b45c2b2bb61c26644f51ff664de75 |
| backend/tools/__init__.py | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| backend/tools/query_tools.py | 251 | e42c403757175cefceca201c083ff9444e8e2a1af95769b9185d6074fd35fa6c |
| requirements.txt | 22 | 8422a04685a05ca08514c78eca7048958797380ea3b552ac0d9bbcd29dd908aa |

합계: 318개 파일
