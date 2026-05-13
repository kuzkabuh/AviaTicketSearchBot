"""Seed registry of airlines and official news/promotion sources."""

from __future__ import annotations

SEED_AIRLINES: list[dict[str, object]] = [
    {"airline_code": "SU", "icao_code": "AFL", "official_name": "Aeroflot", "display_name_ru": "Аэрофлот", "display_name_en": "Aeroflot", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.aeroflot.ru", "news_source_status": "configured"},
    {"airline_code": "DP", "icao_code": "PBD", "official_name": "Pobeda", "display_name_ru": "Победа", "display_name_en": "Pobeda", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.pobeda.aero", "news_source_status": "configured"},
    {"airline_code": "FV", "icao_code": "SDM", "official_name": "Rossiya Airlines", "display_name_ru": "Россия", "display_name_en": "Rossiya Airlines", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.rossiya-airlines.ru", "news_source_status": "configured"},
    {"airline_code": "S7", "icao_code": "SBI", "official_name": "S7 Airlines", "display_name_ru": "S7 Airlines", "display_name_en": "S7 Airlines", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.s7.ru", "news_source_status": "configured"},
    {"airline_code": "U6", "icao_code": "SVR", "official_name": "Ural Airlines", "display_name_ru": "Уральские авиалинии", "display_name_en": "Ural Airlines", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.uralairlines.ru", "news_source_status": "configured"},
    {"airline_code": "UT", "icao_code": "UTA", "official_name": "UTair", "display_name_ru": "Utair", "display_name_en": "UTair", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.utair.ru", "news_source_status": "configured"},
    {"airline_code": "N4", "icao_code": "NWS", "official_name": "Nordwind Airlines", "display_name_ru": "Nordwind Airlines", "display_name_en": "Nordwind Airlines", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://nordwindairlines.ru", "news_source_status": "configured"},
    {"airline_code": "5N", "icao_code": "AUL", "official_name": "Smartavia", "display_name_ru": "Smartavia", "display_name_en": "Smartavia", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://flysmartavia.com", "news_source_status": "configured"},
    {"airline_code": "WZ", "icao_code": "RWZ", "official_name": "Red Wings", "display_name_ru": "Red Wings", "display_name_en": "Red Wings", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://flyredwings.com", "news_source_status": "configured"},
    {"airline_code": "A4", "icao_code": "AZO", "official_name": "Azimuth", "display_name_ru": "Азимут", "display_name_en": "Azimuth", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://azimuth.aero", "news_source_status": "configured"},
    {"airline_code": "HZ", "icao_code": "SHU", "official_name": "Aurora", "display_name_ru": "Аврора", "display_name_en": "Aurora", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://flyaurora.ru", "news_source_status": "configured"},
    {"airline_code": "Y7", "icao_code": "TYA", "official_name": "NordStar", "display_name_ru": "NordStar", "display_name_en": "NordStar", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.nordstar.ru", "news_source_status": "configured"},
    {"airline_code": "YC", "icao_code": "LLM", "official_name": "Yamal Airlines", "display_name_ru": "Ямал", "display_name_en": "Yamal Airlines", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://yamal.aero", "news_source_status": "configured"},
    {"airline_code": "R3", "icao_code": "SYL", "official_name": "Yakutia Airlines", "display_name_ru": "Якутия", "display_name_en": "Yakutia Airlines", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.yakutia.aero", "news_source_status": "configured"},
    {"airline_code": "EO", "icao_code": "KAR", "official_name": "Ikar / Pegas Fly", "display_name_ru": "Икар / Pegas Fly", "display_name_en": "Ikar / Pegas Fly", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://pegasfly.com", "news_source_status": "requires_manual_setup"},
    {"airline_code": "IO", "icao_code": "IAE", "official_name": "IrAero", "display_name_ru": "ИрАэро", "display_name_en": "IrAero", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://iraero.ru", "news_source_status": "configured"},
    {"airline_code": "RT", "icao_code": "BUG", "official_name": "UVT Aero", "display_name_ru": "ЮВТ Аэро", "display_name_en": "UVT Aero", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://uvtaero.ru", "news_source_status": "configured"},
    {"airline_code": "D2", "icao_code": "SSF", "official_name": "Severstal Aircompany", "display_name_ru": "Северсталь Авиа", "display_name_en": "Severstal Aircompany", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://severstal-avia.ru", "news_source_status": "requires_manual_setup"},
    {"airline_code": "7R", "icao_code": "RLU", "official_name": "RusLine", "display_name_ru": "РусЛайн", "display_name_en": "RusLine", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.rusline.aero", "news_source_status": "requires_manual_setup"},
    {"airline_code": "6R", "icao_code": "DRU", "official_name": "Alrosa", "display_name_ru": "Алроса", "display_name_en": "Alrosa", "country_code": "RU", "country_name": "Russia", "is_russian": 1, "official_website": "https://www.alrosa.aero", "news_source_status": "requires_manual_setup"},
    {"airline_code": "QR", "icao_code": "QTR", "official_name": "Qatar Airways", "display_name_ru": "Qatar Airways", "display_name_en": "Qatar Airways", "country_code": "QA", "country_name": "Qatar", "is_russian": 0, "official_website": "https://www.qatarairways.com", "news_source_status": "configured"},
    {"airline_code": "EK", "icao_code": "UAE", "official_name": "Emirates", "display_name_ru": "Emirates", "display_name_en": "Emirates", "country_code": "AE", "country_name": "United Arab Emirates", "is_russian": 0, "official_website": "https://www.emirates.com", "news_source_status": "configured"},
]

# Official airline pages only. Most Russian sites do not expose stable public RSS,
# so HTML sources are configured with broad, conservative selectors.
SEED_SOURCES: list[dict[str, object]] = [
    {"airline_code": "SU", "source_name": "Aeroflot news", "source_type": "html", "source_url": "https://www.aeroflot.ru/ru-ru/news", "source_role": "news", "language_code": "ru"},
    {"airline_code": "DP", "source_name": "Pobeda news", "source_type": "html", "source_url": "https://www.pobeda.aero/information/news", "source_role": "news", "language_code": "ru"},
    {"airline_code": "FV", "source_name": "Rossiya news", "source_type": "html", "source_url": "https://www.rossiya-airlines.ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "S7", "source_name": "S7 news", "source_type": "html", "source_url": "https://www.s7.ru/ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "U6", "source_name": "Ural Airlines news", "source_type": "html", "source_url": "https://www.uralairlines.ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "UT", "source_name": "Utair news", "source_type": "html", "source_url": "https://www.utair.ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "N4", "source_name": "Nordwind news", "source_type": "html", "source_url": "https://nordwindairlines.ru/ru/news", "source_role": "news", "language_code": "ru"},
    {"airline_code": "5N", "source_name": "Smartavia news", "source_type": "html", "source_url": "https://flysmartavia.com/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "WZ", "source_name": "Red Wings news", "source_type": "html", "source_url": "https://flyredwings.com/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "A4", "source_name": "Azimuth news", "source_type": "html", "source_url": "https://azimuth.aero/ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "HZ", "source_name": "Aurora news", "source_type": "html", "source_url": "https://flyaurora.ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "Y7", "source_name": "NordStar news", "source_type": "html", "source_url": "https://www.nordstar.ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "YC", "source_name": "Yamal news", "source_type": "html", "source_url": "https://yamal.aero/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "R3", "source_name": "Yakutia news", "source_type": "html", "source_url": "https://www.yakutia.aero/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "IO", "source_name": "IrAero news", "source_type": "html", "source_url": "https://iraero.ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "RT", "source_name": "UVT Aero news", "source_type": "html", "source_url": "https://uvtaero.ru/about/news/", "source_role": "news", "language_code": "ru"},
    {"airline_code": "QR", "source_name": "Qatar Airways press releases", "source_type": "html", "source_url": "https://www.qatarairways.com/press-releases/en-WW", "source_role": "press", "language_code": "en"},
    {"airline_code": "EK", "source_name": "Emirates media centre", "source_type": "html", "source_url": "https://www.emirates.com/media-centre/", "source_role": "press", "language_code": "en"},
]
