# https://hakibenita.com/fast-load-data-python-postgresql

from typing import Iterator, Dict, Any, Optional
from urllib.parse import urlencode
import datetime


#------------------------ Profile

import time
from functools import wraps
from memory_profiler import memory_usage


def profile(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        fn_kwargs_str = ', '.join(f'{k}={v}' for k, v in kwargs.items())
        print(f'\n{fn.__name__}({fn_kwargs_str})')

        # Measure time
        t = time.perf_counter()
        retval = fn(*args, **kwargs)
        elapsed = time.perf_counter() - t
        print(f'Time   {elapsed:0.4}')

        # Measure memory
        mem, retval = memory_usage((fn, args, kwargs), retval=True, timeout=200, interval=1e-7)

        print(f'Memory {max(mem) - min(mem)}')
        return retval

    return inner


#------------------------ Data

import requests

def iter_beers_from_api(page_size: int = 25) -> Iterator[Dict[str, Any]]:
    session = requests.Session()
    page = 1
    while True:
        response = session.get('https://api.punkapi.com/v2/beers?' + urlencode({
            'page': page,
            'per_page': page_size
        }))
        response.raise_for_status()

        data = response.json()
        if not data:
            break

        for beer in data:
            yield beer

        page += 1


def iter_beers_from_file(path: str) -> Iterator[Dict[str, Any]]:
    import json
    with open(path, 'r') as f:
        data = json.load(f)
        for beer in data:
            yield beer


#------------------------ Load

def create_staging_table(cursor):
    cursor.execute("""
        DROP TABLE IF EXISTS staging_beers;
        CREATE TABLE staging_beers (
            id                  INTEGER,
            name                TEXT,
            tagline             TEXT,
            first_brewed        DATE,
            description         TEXT,
            image_url           TEXT,
            abv                 DECIMAL,
            ibu                 DECIMAL,
            target_fg           DECIMAL,
            target_og           DECIMAL,
            ebc                 DECIMAL,
            srm                 DECIMAL,
            ph                  DECIMAL,
            attenuation_level   DECIMAL,
            brewers_tips        TEXT,
            contributed_by      TEXT,
            volume              INTEGER
        );
    """)


def parse_first_brewed(text: str) -> datetime.date:
    parts = text.split('/')
    if len(parts) == 2:
        return datetime.date(int(parts[1]), int(parts[0]), 1)
    elif len(parts) == 1:
        return datetime.date(int(parts[0]), 1, 1)
    else:
        assert False, 'Unknown date format'


@profile
def insert_one_by_one(connection, beers: Iterator[Dict[str, Any]]) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)
        for beer in beers:
            cursor.execute("""
                INSERT INTO staging_beers VALUES (
                    %(id)s,
                    %(name)s,
                    %(tagline)s,
                    %(first_brewed)s,
                    %(description)s,
                    %(image_url)s,
                    %(abv)s,
                    %(ibu)s,
                    %(target_fg)s,
                    %(target_og)s,
                    %(ebc)s,
                    %(srm)s,
                    %(ph)s,
                    %(attenuation_level)s,
                    %(brewers_tips)s,
                    %(contributed_by)s,
                    %(volume)s
                );
            """, {
                **beer,
                'first_brewed': parse_first_brewed(beer['first_brewed']),
                'volume': beer['volume']['value'],
            })


# http://initd.org/psycopg/docs/cursor.html#cursor.executemany

@profile
def insert_executemany(connection, beers: Iterator[Dict[str, Any]]) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)

        all_beers = [{
            **beer,
            'first_brewed': parse_first_brewed(beer['first_brewed']),
            'volume': beer['volume']['value'],
        } for beer in beers]

        cursor.executemany("""
            INSERT INTO staging_beers VALUES (
                %(id)s,
                %(name)s,
                %(tagline)s,
                %(first_brewed)s,
                %(description)s,
                %(image_url)s,
                %(abv)s,
                %(ibu)s,
                %(target_fg)s,
                %(target_og)s,
                %(ebc)s,
                %(srm)s,
                %(ph)s,
                %(attenuation_level)s,
                %(brewers_tips)s,
                %(contributed_by)s,
                %(volume)s
            );
        """, all_beers)


@profile
def insert_executemany_iterator(connection, beers: Iterator[Dict[str, Any]]) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)
        cursor.executemany("""
            INSERT INTO staging_beers VALUES (
                %(id)s,
                %(name)s,
                %(tagline)s,
                %(first_brewed)s,
                %(description)s,
                %(image_url)s,
                %(abv)s,
                %(ibu)s,
                %(target_fg)s,
                %(target_og)s,
                %(ebc)s,
                %(srm)s,
                %(ph)s,
                %(attenuation_level)s,
                %(brewers_tips)s,
                %(contributed_by)s,
                %(volume)s
            );
        """, ({
            **beer,
            'first_brewed': parse_first_brewed(beer['first_brewed']),
            'volume': beer['volume']['value'],
        } for beer in beers))


# http://initd.org/psycopg/docs/extras.html#psycopg2.extras.execute_batch
import psycopg2.extras


@profile
def insert_execute_batch(connection, beers: Iterator[Dict[str, Any]], page_size: int = 100) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)

        all_beers = [{
            **beer,
            'first_brewed': parse_first_brewed(beer['first_brewed']),
            'volume': beer['volume']['value'],
        } for beer in beers]

        psycopg2.extras.execute_batch(cursor, """
            INSERT INTO staging_beers VALUES (
                %(id)s,
                %(name)s,
                %(tagline)s,
                %(first_brewed)s,
                %(description)s,
                %(image_url)s,
                %(abv)s,
                %(ibu)s,
                %(target_fg)s,
                %(target_og)s,
                %(ebc)s,
                %(srm)s,
                %(ph)s,
                %(attenuation_level)s,
                %(brewers_tips)s,
                %(contributed_by)s,
                %(volume)s
            );
        """, all_beers, page_size=page_size)


@profile
def insert_execute_batch_iterator(connection, beers: Iterator[Dict[str, Any]], page_size: int = 100) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)

        iter_beers = ({
            **beer,
            'first_brewed': parse_first_brewed(beer['first_brewed']),
            'volume': beer['volume']['value'],
        } for beer in beers)

        psycopg2.extras.execute_batch(cursor, """
            INSERT INTO staging_beers VALUES (
                %(id)s,
                %(name)s,
                %(tagline)s,
                %(first_brewed)s,
                %(description)s,
                %(image_url)s,
                %(abv)s,
                %(ibu)s,
                %(target_fg)s,
                %(target_og)s,
                %(ebc)s,
                %(srm)s,
                %(ph)s,
                %(attenuation_level)s,
                %(brewers_tips)s,
                %(contributed_by)s,
                %(volume)s
            );
        """, iter_beers, page_size=page_size)


# http://initd.org/psycopg/docs/extras.html#psycopg2.extras.execute_values
import psycopg2.extras

@profile
def insert_execute_values(connection, beers: Iterator[Dict[str, Any]]) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO staging_beers VALUES %s;
        """, [(
            beer['id'],
            beer['name'],
            beer['tagline'],
            parse_first_brewed(beer['first_brewed']),
            beer['description'],
            beer['image_url'],
            beer['abv'],
            beer['ibu'],
            beer['target_fg'],
            beer['target_og'],
            beer['ebc'],
            beer['srm'],
            beer['ph'],
            beer['attenuation_level'],
            beer['brewers_tips'],
            beer['contributed_by'],
            beer['volume']['value'],
        ) for beer in beers])



@profile
def insert_execute_values_iterator(connection, beers: Iterator[Dict[str, Any]], page_size: int = 100) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)

        psycopg2.extras.execute_values(cursor, """
            INSERT INTO staging_beers VALUES %s;
        """, ((
            beer['id'],
            beer['name'],
            beer['tagline'],
            parse_first_brewed(beer['first_brewed']),
            beer['description'],
            beer['image_url'],
            beer['abv'],
            beer['ibu'],
            beer['target_fg'],
            beer['target_og'],
            beer['ebc'],
            beer['srm'],
            beer['ph'],
            beer['attenuation_level'],
            beer['brewers_tips'],
            beer['contributed_by'],
            beer['volume']['value'],
        ) for beer in beers), page_size=page_size)


# http://initd.org/psycopg/docs/cursor.html#cursor.copy_from
# https://docs.python.org/3.7/library/io.html?io.StringIO#io.StringIO
import io

def clean_csv_value(value: Optional[Any]) -> str:
    if value is None:
        return r'\N'
    return str(value).replace('\n', '\\n')


@profile
def copy_stringio(connection, beers: Iterator[Dict[str, Any]]) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)
        csv_file_like_object = io.StringIO()
        for beer in beers:
            csv_file_like_object.write('|'.join(map(clean_csv_value, (
                beer['id'],
                beer['name'],
                beer['tagline'],
                parse_first_brewed(beer['first_brewed']),
                beer['description'],
                beer['image_url'],
                beer['abv'],
                beer['ibu'],
                beer['target_fg'],
                beer['target_og'],
                beer['ebc'],
                beer['srm'],
                beer['ph'],
                beer['attenuation_level'],
                beer['contributed_by'],
                beer['brewers_tips'],
                beer['volume']['value'],
            ))) + '\n')
        csv_file_like_object.seek(0)
        cursor.copy_from(csv_file_like_object, 'staging_beers', sep='|')


class StringIteratorIO(io.TextIOBase):

    def __init__(self, iter: Iterator[str]):
        self._iter = iter
        self._buff = ''

    def readable(self) -> bool:
        return True

    def _read1(self, n: Optional[int] = None) -> str:
        while not self._buff:
            try:
                self._buff = next(self._iter)
            except StopIteration:
                break
        ret = self._buff[:n]
        self._buff = self._buff[len(ret):]
        return ret

    def read(self, n: Optional[int] = None) -> str:
        line = []
        if n is None or n < 0:
            while True:
                m = self._read1()
                if not m:
                    break
                line.append(m)
        else:
            while n > 0:
                m = self._read1(n)
                if not m:
                    break
                n -= len(m)
                line.append(m)
        return ''.join(line)


@profile
def copy_string_iterator(connection, beers: Iterator[Dict[str, Any]], size: int = 8192) -> None:
    with connection.cursor() as cursor:
        create_staging_table(cursor)

        beers_string_iterator = StringIteratorIO((
            '|'.join(map(clean_csv_value, (
                beer['id'],
                beer['name'],
                beer['tagline'],
                parse_first_brewed(beer['first_brewed']).isoformat(),
                beer['description'],
                beer['image_url'],
                beer['abv'],
                beer['ibu'],
                beer['target_fg'],
                beer['target_og'],
                beer['ebc'],
                beer['srm'],
                beer['ph'],
                beer['attenuation_level'],
                beer['brewers_tips'],
                beer['contributed_by'],
                beer['volume']['value'],
            ))) + '\n'
            for beer in beers
        ))

        cursor.copy_from(beers_string_iterator, 'staging_beers', sep='|', size=size)


#------------------------ Benchmark

'''
connection = psycopg2.connect(
    host='localhost',
    database='testload',
    user='haki',
    password=None,
)
connection.set_session(autocommit=True)

from psycopg2.extras import NamedTupleCursor

def test(connection, n: int):
    # Make sure the data was loaded
    with connection.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor) as cursor:
        # Test number of rows.
        cursor.execute('SELECT COUNT(*) AS cnt FROM staging_beers')
        record = cursor.fetchone()
        assert record.cnt == n, f'Expected {n} rows, got {rowcount} rows!'

        # Test that the data was loaded, and that transformations were applied correctly.
        cursor.execute("""
            SELECT DISTINCT ON (id)
                *
            FROM
                staging_beers
            WHERE
                id IN (1, 235)
            ORDER BY
                id;
        """)
        beer_1 = cursor.fetchone()
        assert beer_1.name == 'Buzz'
        assert beer_1.first_brewed == datetime.date(2007, 9, 1)
        assert beer_1.volume == 20

        beer_235 = cursor.fetchone()
        assert beer_235.name == 'Mango And Chili Barley Wine'
        assert beer_235.first_brewed == datetime.date(2016, 1, 1)
        assert beer_235.volume == 20


beers = list(iter_beers_from_api()) * 100

insert_one_by_one(connection, beers)
test(connection, len(beers))

insert_executemany(connection, beers)
test(connection, len(beers))

insert_executemany_iterator(connection, beers)
test(connection, len(beers))

insert_execute_batch(connection, beers)
test(connection, len(beers))

insert_execute_batch_iterator(connection, beers, page_size=1)
test(connection, len(beers))

insert_execute_batch_iterator(connection, beers, page_size=100)
test(connection, len(beers))

insert_execute_batch_iterator(connection, beers, page_size=1000)
test(connection, len(beers))

insert_execute_batch_iterator(connection, beers, page_size=10000)
test(connection, len(beers))

insert_execute_values(connection, beers)
test(connection, len(beers))

insert_execute_values_iterator(connection, beers, page_size=1)
test(connection, len(beers))

insert_execute_values_iterator(connection, beers, page_size=100)
test(connection, len(beers))

insert_execute_values_iterator(connection, beers, page_size=1000)
test(connection, len(beers))

insert_execute_values_iterator(connection, beers, page_size=10000)
test(connection, len(beers))

copy_stringio(connection, beers)
test(connection, len(beers))

copy_string_iterator(connection, beers, size=1024)
test(connection, len(beers))

copy_string_iterator(connection, beers, size=1024 * 8)
test(connection, len(beers))

copy_string_iterator(connection, beers, size=1024 * 16)
test(connection, len(beers))

copy_string_iterator(connection, beers, size=1024 * 64)'''