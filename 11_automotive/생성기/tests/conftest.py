"""시험은 프로필이 정해져 있어야 설정을 읽는다. 따로 정하지 않으면 영상용(video)으로 돈다 (MOM_PROFILE=final pytest 로 최종용도 시험 가능)."""
import os

os.environ.setdefault("MOM_PROFILE", "video")
