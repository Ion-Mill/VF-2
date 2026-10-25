-- 생성: tools/gen_dev_users.py — 개발·시연 전용 계정 (비밀번호는 README 참고). 운영 금지
INSERT INTO app_user (user_id, user_name, role_code, home_shift_type, home_process_code, home_process_code_2, password_hash) VALUES
  ('U01', '김하늘', 'OPR', 'DAY', 'OP-10', 'OP-20', 'scrypt$16384$8$1$3lUiDVX4P+pFfwtWzT0p9A==$QohmchuVq9rDMS2KWlUTCgBwdGRSOQfTVjgRPorDKgg='),
  ('U02', '이서연', 'OPR', 'DAY', 'OP-30', NULL, 'scrypt$16384$8$1$kGjQbs384rU6Okftf0lyFA==$bXdGC6eyvMd+kDL2QPyAsUS1R2LE8Kg6Oq0F/r87jXs='),
  ('U03', '박준호', 'OPR', 'DAY', 'OP-50', 'OP-40', 'scrypt$16384$8$1$+S6gufePq2wFl9zUxZQuGg==$RyZ1u66X+o8B6tTWHs50l2RhlcaSMEHXmnv9raS8LDM='),
  ('U04', '최민재', 'OPR', 'NIGHT', 'OP-10', 'OP-20', 'scrypt$16384$8$1$Qog1X9QfXM+sLCbylcLJ2Q==$K+Wd9OUW3qhXw3VH8rOj7E4ha3SPzyKT3uu0CUNge4M='),
  ('U05', '정유진', 'OPR', 'NIGHT', 'OP-30', NULL, 'scrypt$16384$8$1$GWYBvtj1P4dduPg6TzlUbA==$eeH3N5hxoi5a9LDZWTN2OwyneFVllq+lYUtfc+us9mE='),
  ('U06', '강태윤', 'OPR', 'NIGHT', 'OP-50', 'OP-40', 'scrypt$16384$8$1$3VcDVEbJsWoIFvTdBY+YaA==$1RvT4hJ9hDnVaC5THcM2ZSY/fMCqem5qcmcymmLpT6I='),
  ('U07', '이도윤', 'MNT', 'DAY', NULL, NULL, 'scrypt$16384$8$1$5fguZK9htkO8EDM5jv/SXQ==$GzQmFoIH1WFPRBoM0CKjsEKjWrJtCdqmk7Jrot0X7EM='),
  ('U08', '한지훈', 'MNT', 'DAY', NULL, NULL, 'scrypt$16384$8$1$6qxYWp8vBitb1nZ+GA1FWg==$wSWYBi6UwPDHiziFqhldo7J9eK1JW5bDyZJjuYU/jvU='),
  ('U09', '오세린', 'MNT', 'NIGHT', NULL, NULL, 'scrypt$16384$8$1$tsbI7ZdhsYUOees7cC/HpQ==$cLskYD2CFjYR86Vidh0l877WN8ZLOYC3t9qhOFkqPqQ='),
  ('U10', '박서준', 'SUP', 'DAY', NULL, NULL, 'scrypt$16384$8$1$+CzoZHMtPCJF4RZFNLxoag==$AdZL0QFS6kFTYjNHnsHZZYO25VyEp/EcMJahB1avh6Q='),
  ('U11', '윤가은', 'SUP', 'NIGHT', NULL, NULL, 'scrypt$16384$8$1$mLyNmmrKURlvF7Y5yy+tIg==$olFZsPy9mjwlaOG9AFx/ZUq6tm5JcRyrklgSBzRGuvY='),
  ('U12', '장현우', 'MGR', 'DAY', NULL, NULL, 'scrypt$16384$8$1$otu5mTEKSZ5uDNtBFsxo8Q==$HII0/ysCpvEsOHv8qlKlKpdLW0gNqQZixpJVZ3TC+uE=');
UPDATE internal_doc SET approved_by = 'U12', approved_at = '2026-10-07 09:00+09';
