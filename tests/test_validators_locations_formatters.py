import unittest

from services.locations import find_locations, get_location_by_code
from utils.formatters import format_offer
from utils.validators import validate_api_date, validate_iata_format


class ValidatorsLocationsFormattersTest(unittest.TestCase):
    def test_validate_api_date_accepts_month_and_day(self):
        self.assertTrue(validate_api_date("2026-06"))
        self.assertTrue(validate_api_date("2026-06-15"))
        self.assertFalse(validate_api_date("15.06.2026"))

    def test_location_resolver_accepts_russian_city_and_iata(self):
        self.assertEqual(find_locations("Москва")[0].code, "MOW")
        self.assertEqual(find_locations("казань")[0].code, "KZN")
        self.assertEqual(get_location_by_code("aer").code, "AER")
        self.assertTrue(validate_iata_format("LED"))

    def test_format_offer_contains_cache_notice_link_and_price(self):
        text = format_offer(
            {
                "origin": "MOW",
                "destination": "KZN",
                "origin_city": "Москва",
                "destination_city": "Казань",
                "origin_airport": "все аэропорты",
                "destination_airport": "Казань",
                "date": "2026-06-15",
                "departure_time": "10:00",
                "arrival_time": "11:30",
                "duration": 90,
                "transfers": 0,
                "airline": "SU",
                "flight_number": "123",
                "price": 5000,
                "currency": "RUB",
                "link": "https://www.aviasales.ru/search/MOW1506KZN1",
            },
            1,
            2,
        )
        self.assertIn("Москва → Казань", text)
        self.assertIn("10 000 ₽", text)
        self.assertIn("Купить билет", text)


if __name__ == "__main__":
    unittest.main()
