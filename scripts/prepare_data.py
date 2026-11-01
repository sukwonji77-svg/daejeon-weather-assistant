"""1단계: 대전의 공개 기온 데이터를 검증하고 CSV와 요약을 만듭니다.

기본 실행은 이미 받은 원본을 사용합니다. --download를 붙이면 다시 받습니다.
외부 패키지를 설치하지 않아도 실행할 수 있습니다.
"""

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE_URL = "https://archive-api.open-meteo.com/v1/archive?" + urlencode({
    "latitude": 36.3504,
    "longitude": 127.3845,
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "daily": "temperature_2m_mean",
    "timezone": "Asia/Seoul",
})


def prepare(download=False):
    DATA.mkdir(parents=True, exist_ok=True)
    raw_path = DATA / "open_meteo_2025_raw.json"
    if download or not raw_path.exists():
        print("Open-Meteo에서 대전 기온을 가져옵니다...")
        with urlopen(SOURCE_URL, timeout=60) as response:
            raw = json.load(response)
        # 정상 응답인지 확인한 뒤 원본을 보관합니다.
        if "daily" not in raw:
            raise ValueError("기온 데이터 응답이 아닙니다.")
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    raw = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    daily = raw["daily"]
    dates = daily["time"]
    values = daily["temperature_2m_mean"]
    expected_dates = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(365)]
    if dates != expected_dates or len(values) != 365:
        raise ValueError("2025년 1월 1일부터 12월 31일까지 365건이 필요합니다.")
    if raw.get("daily_units", {}).get("temperature_2m_mean") != "°C":
        raise ValueError("기온 단위가 섭씨가 아닙니다.")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        raise ValueError("누락되거나 올바르지 않은 기온이 있습니다.")

    # 과제의 기본 데이터 구조: date, value, memo
    records = [{"date": day, "value": value, "memo": "대전 / Open-Meteo 재분석 일평균기온 (°C)"}
               for day, value in zip(dates, values)]
    with (DATA / "daejeon_temperature_2025.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["date", "value", "memo"])
        writer.writeheader()
        writer.writerows(records)
    (DATA / "daejeon_temperature_2025.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    months = defaultdict(list)
    for record in records:
        months[record["date"][:7]].append(record["value"])
    monthly = [{"month": month, "count": len(items), "average": round(mean(items), 2)}
               for month, items in sorted(months.items())]
    max_value, min_value = max(values), min(values)
    difference = round(monthly[-1]["average"] - monthly[-2]["average"], 2)
    trend = "상승" if difference > 0 else "하락" if difference < 0 else "유지"
    summary = {
        "city": "대전", "period": f"{dates[0]} ~ {dates[-1]}", "count": len(records),
        "unit": "°C", "metric": "일평균기온",
        "metrics": {"average": round(mean(values), 2), "max": max_value, "min": min_value},
        "warmest_dates": [r["date"] for r in records if r["value"] == max_value],
        "coldest_dates": [r["date"] for r in records if r["value"] == min_value],
        "monthly": monthly,
        "trend": {"comparison": "2025년 12월 평균 - 11월 평균", "difference_celsius": difference, "direction": trend},
        "source": {"provider": "Open-Meteo", "url": SOURCE_URL,
                   "docs": "https://open-meteo.com/en/docs/historical-weather-api",
                   "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
                   "requested_coordinates": {"latitude": 36.3504, "longitude": 127.3845},
                   "returned_grid_coordinates": {"latitude": raw.get("latitude"), "longitude": raw.get("longitude")},
                   "note": "대전 대표 좌표에 대응하는 격자 재분석 데이터입니다. 기상청 특정 관측소 실측치나 대전 전역 평균이 아닙니다."},
    }
    (DATA / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = ["# 대전 기온 분석: 첫 실습 결과", "",
              "출처: [Open-Meteo](https://open-meteo.com/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)", "",
              "대전 대표 좌표(36.3504, 127.3845)의 재분석 데이터입니다. 특정 관측소 실측치나 대전 전역 평균은 아닙니다.", "",
              f"- 기간: {summary['period']}", f"- 데이터 수: {len(records)}건 / 누락 없음",
              f"- 연평균 기온: {summary['metrics']['average']}℃",
              f"- 일평균 기온이 가장 높은 날: {', '.join(summary['warmest_dates'])} / {max_value}℃",
              f"- 일평균 기온이 가장 낮은 날: {', '.join(summary['coldest_dates'])} / {min_value}℃",
              f"- 12월 평균과 11월 평균의 차이: {difference:+.2f}℃ ({trend})", "",
              "‘가장 높은 기온’은 여기서 일평균의 최댓값이며, 하루 중 순간 최고기온과 다릅니다.", "",
              "## 월별 평균", "", "| 월 | 날짜 수 | 평균기온(℃) |", "|---|---:|---:|"]
    report += [f"| {m['month']} | {m['count']} | {m['average']:.2f} |" for m in monthly]
    report += ["", "추세는 2025년 12월과 11월의 비교입니다. 현재 날씨나 장기 기후변화를 의미하지 않습니다.", ""]
    (ROOT / "분석결과.md").write_text("\n".join(report), encoding="utf-8")
    print(f"완료: {len(records)}건, 누락 없음, 평균 {summary['metrics']['average']}℃")
    print(f"결과 폴더: {DATA}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="공개 데이터를 다시 내려받습니다")
    args = parser.parse_args()
    try:
        prepare(args.download)
    except Exception as error:
        raise SystemExit(f"데이터 준비 실패: {error}")
