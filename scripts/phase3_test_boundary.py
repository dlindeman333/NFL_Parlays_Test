#!/usr/bin/env python3
"""Fail-closed boundary for TEST-only scheduled jobs using privileged credentials."""
import argparse
import os
from urllib.parse import urlsplit

TEST_REPOSITORY = 'dlindeman333/NFL_Parlays_Test'
TEST_PROJECT = 'luxezjthznupdghmexyh'


def validate(repository, supabase_url):
    if repository != TEST_REPOSITORY:
        raise ValueError('Refusing to run outside the designated TEST GitHub repository')
    parsed = urlsplit(supabase_url or '')
    if (parsed.scheme != 'https' or parsed.hostname != f'{TEST_PROJECT}.supabase.co'
            or parsed.username or parsed.password or parsed.port or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise ValueError('Refusing to run against an unrecognized Supabase TEST project')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', default=os.getenv('GITHUB_REPOSITORY', ''))
    parser.add_argument('--supabase-url', default=os.getenv('SUPABASE_URL', ''))
    args = parser.parse_args()
    validate(args.repository, args.supabase_url)
    print('TEST repository and Supabase project boundary verified')


if __name__ == '__main__':
    main()
