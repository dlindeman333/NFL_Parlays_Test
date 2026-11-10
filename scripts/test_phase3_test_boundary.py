import unittest
from phase3_test_boundary import validate


class TestBoundary(unittest.TestCase):
    def test_correct_test_scope(self):
        self.assertTrue(validate('dlindeman333/NFL_Parlays_Test', 'https://luxezjthznupdghmexyh.supabase.co'))

    def test_wrong_repo(self):
        with self.assertRaises(ValueError):
            validate('dlindeman333/NFL_Parlays', 'https://luxezjthznupdghmexyh.supabase.co')

    def test_production_project(self):
        with self.assertRaises(ValueError):
            validate('dlindeman333/NFL_Parlays_Test', 'https://wpvuunwtyxycqfjwuzkn.supabase.co')

    def test_invalid_urls(self):
        for url in ('http://luxezjthznupdghmexyh.supabase.co',
                    'https://luxezjthznupdghmexyh.supabase.co.evil.test',
                    'https://luxezjthznupdghmexyh.supabase.co@evil.test',
                    'https://luxezjthznupdghmexyh.supabase.co/rest/v1', ''):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate('dlindeman333/NFL_Parlays_Test', url)


if __name__ == '__main__':
    unittest.main()
