import logging
import unittest


from api import GROUPED_PRICES_ENDPOINT, PRICES_FOR_DATES_ENDPOINT, TravelPayoutsAPI
from config import Settings


class FakeTravelPayoutsAPI(TravelPayoutsAPI):
    def __init__(self, payloads):
        super().__init__()
        self.payloads = payloads
        self.calls = []

    async def _make_request(self, endpoint, params):
        self.calls.append((endpoint, params))
        return self.payloads.get(endpoint)


logging.disable(logging.CRITICAL)


class AviasalesApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_prices_for_dates_normalizes_successful_payload(self):
        client = FakeTravelPayoutsAPI(
            {
                PRICES_FOR_DATES_ENDPOINT: {
                    "success": True,
                    "currency": "rub",
                    "data": [
                        {
                            "origin": "MOW",
                            "destination": "KZN",
                            "origin_airport": "SVO",
                            "destination_airport": "KZN",
                            "price": 4200,
                            "airline": "SU",
                            "flight_number": "1192",
                            "departure_at": "2026-06-15T09:00:00+03:00",
                            "transfers": 0,
                            "duration": 95,
                            "link": "/MOW1506KZN1",
                        }
                    ],
                }
            }
        )
        offers = await client.search_cheap_tickets("MOW", "KZN", "2026-06-15", limit=1)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["price"], 4200)
        self.assertEqual(offers[0]["link"], "https://www.aviasales.ru/MOW1506KZN1")
        self.assertEqual(client.calls[0][0], PRICES_FOR_DATES_ENDPOINT)
        self.assertNotIn("token", client.calls[0][1])

    async def test_empty_or_invalid_payload_returns_empty_list(self):
        client = FakeTravelPayoutsAPI({PRICES_FOR_DATES_ENDPOINT: {"success": False, "data": {}, "error": "bad"}})
        offers = await client.search_cheap_tickets("MOW", "KZN", "2026-06-15", limit=1)
        self.assertEqual(offers, [])

    async def test_grouped_prices_skips_expired_price(self):
        client = FakeTravelPayoutsAPI(
            {
                GROUPED_PRICES_ENDPOINT: {
                    "success": True,
                    "data": {
                        "2026-06-15": {
                            "origin": "MOW",
                            "destination": "KZN",
                            "price": 1000,
                            "departure_at": "2026-06-15T09:00:00+03:00",
                            "expires_at": "2000-01-01T00:00:00+00:00",
                        }
                    },
                }
            }
        )
        offers = await client.get_calendar_prices("MOW", "KZN", "2026-06-15")
        self.assertEqual(offers, [])


class ConfigTest(unittest.TestCase):
    def test_settings_validation_requires_tokens(self):
        settings = Settings(bot_token="", travelpayouts_token="")
        with self.assertRaises(ValueError):
            settings.validate()


if __name__ == "__main__":
    unittest.main()

class RoundTripAviasalesApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_request_uses_return_at_and_one_way_false(self):
        client = FakeTravelPayoutsAPI(
            {
                PRICES_FOR_DATES_ENDPOINT: {
                    "success": True,
                    "data": [
                        {
                            "origin": "MOW",
                            "destination": "KZN",
                            "price": 18300,
                            "airline": "N4",
                            "flight_number": "123",
                            "departure_at": "2026-05-25T20:40:00+03:00",
                            "return_at": "2026-05-28T10:10:00+03:00",
                            "transfers": 0,
                            "return_transfers": 1,
                            "duration_to": 95,
                            "duration_back": 110,
                            "duration": 205,
                        }
                    ],
                }
            }
        )
        offers = await client.search_cheap_tickets("MOW", "KZN", "2026-05-25", limit=1, trip_type="round_trip", return_date="2026-05-28")
        self.assertEqual(client.calls[0][1]["return_at"], "2026-05-28")
        self.assertEqual(client.calls[0][1]["one_way"], "false")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["trip_type"], "round_trip")
        self.assertTrue(offers[0]["round_trip_confirmed"])
        self.assertEqual(offers[0]["transfers_return"], 1)
        self.assertEqual(offers[0]["duration_to"], 95)
        self.assertIn("Nordwind Airlines (N4)", offers[0]["airline"])

    async def test_one_way_request_omits_return_at_and_uses_one_way_true(self):
        client = FakeTravelPayoutsAPI({PRICES_FOR_DATES_ENDPOINT: {"success": True, "data": []}})
        await client.search_cheap_tickets("MOW", "KZN", "2026-05-25", limit=1, trip_type="one_way")
        self.assertNotIn("return_at", client.calls[0][1])
        self.assertEqual(client.calls[0][1]["one_way"], "true")

    async def test_round_trip_skips_items_without_return_at(self):
        client = FakeTravelPayoutsAPI(
            {
                PRICES_FOR_DATES_ENDPOINT: {
                    "success": True,
                    "data": [
                        {
                            "origin": "MOW",
                            "destination": "KZN",
                            "price": 6136,
                            "airline": "N4",
                            "departure_at": "2026-05-25T20:40:00+03:00",
                        }
                    ],
                },
                GROUPED_PRICES_ENDPOINT: {"success": True, "data": {}},
            }
        )
        offers = await client.search_cheap_tickets("MOW", "KZN", "2026-05-25", limit=1, trip_type="round_trip", return_date="2026-05-28")
        self.assertEqual(offers, [])
