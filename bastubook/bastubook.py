#!/usr/bin/env python3

import sqlite3
import os.path
import logging
import yaml
from sqlite3 import Error
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from logging.handlers import RotatingFileHandler

path = '/path/to/bastubook/'
database = path + 'bookings.db'
chrome_driver = '/path/to/chromedriver'
patrons_file = path + 'patrons.yaml'
logfile = path + 'bastubook.log'
base_url = 'https://baseurlofwebsite/'
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--incognito')
# chrome_options.add_argument('--no-sandbox') # required when running as root
# user. otherwise you would get no sandbox errors.

driver = webdriver.Chrome(executable_path=chrome_driver,
                          chrome_options=chrome_options,
                          service_args=['--verbose',
                                        '--log-path=/tmp/'
                                        'chromedriver.log'])

"""
Setup logging parameters
"""

logger = logging.getLogger("Bastubook Log")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - '
                              '%(name)s - %(levelname)s - %(message)s')
handler = RotatingFileHandler(logfile, maxBytes=50000, backupCount=5)
handler.setFormatter(formatter)
logger.addHandler(handler)


def main():
    """
    Does the database exist? Create if not, then
    continue the script by calling check_booking()
    """
    if os.path.isfile(database):
        pass
    else:
        create_db()

    conn = connect_db(database)

    logger.info('Beginning run...')

    with conn:
        is_bookable(conn)
        check_booking(conn)

    teardown(driver)
    conn.close()


def check_booking(conn):
    """
    Opens the SQL database and checks to see if
    there are any unbooked dates. If not, the script
    exits. If there are, if will continue with
    calling process_booking() and update_booking()
    functions.
    """
    sql = """ SELECT date FROM bookings
                WHERE booked = 'no' AND
                bookable = 'yes' """
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    if not rows:
        logger.info('All available dates are already booked. Exiting..')
    else:
        for row in rows:
            # row[0] prints the first result of the tuple
            date = str(row[0])
            logger.info('DATE: ' + date + ' is not booked. Booking now!')
            process_booking(date)
            update_booking(conn, ('yes', date))


def is_bookable(conn):
    """
    Opens the SQL database and checks for dates
    that are marked as 'unbookable'. A for loop
    will iterate through each date and open
    a selenium session to check for the string defined
    in 'text'. If it is not found, the 'bookable' column
    remains as 'no'. If the text is found, the
    date is changed to 'yes' in the bookable column.
    """
    sql = """ SELECT date FROM bookings
                WHERE bookable = 'no' """

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    if not rows:
        logger.info('There are no dates to book!')
    else:
        for row in rows:
            date = str(row[0])
            text = 'The Public Sauna'

            driver.get(f'{base_url}?rid=30882&date={date}&start={date}%'
                       f'2018:30:00&end={date}%2019:30:00')

            WebDriverWait(driver, 10).until(
                ec.presence_of_element_located((By.NAME, 'fnamn')))
            search_string = driver.find_element_by_class_name('service').text
            if text in search_string:
                sql = """ UPDATE bookings
                          SET bookable = 'yes'
                          WHERE date = ? """
                cur = conn.cursor()
                cur.execute(sql, (date,))
                conn.commit()
                logger.info('DATE: ' + date + ' is now bookable!')
            else:
                logger.info('DATE: ' + date + ' is not yet bookable..')


def add_booking(conn, booking):
    sql = """ INSERT INTO bookings(date, booked)
                VALUES(?,?) """
    cur = conn.cursor()
    cur.execute(sql, booking)
    return cur.lastrowid


def update_booking(conn, booking):
    """
    Called by check_booking() and will set the 'booked' row to
    yes once said date has been successfully booked via the
    process_booking() function.
    """
    sql = """ UPDATE bookings
              SET booked = ?
              WHERE date = ? """
    cur = conn.cursor()
    cur.execute(sql, booking)
    conn.commit()
    return cur.lastrowid


def connect_db(db_file):
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        logger.info(e)

    return None


def create_db():
    logger.info('No database found! Creating a new one..')

    sql_create_table = """CREATE TABLE IF NOT EXISTS bookings (
                              id integer PRIMARY KEY,
                              date text,
                              booked text,
                              bookable text
                              );"""

    conn = connect_db(database)
    if conn is not None:
        c = conn.cursor()
        c.execute(sql_create_table)
        conn.commit()
        conn.close()
    else:
        logger.info('Failed to create a connection to the database!')


def process_booking(date):
    """
    Is called by check_booking() and will proceed with
    booking any dates that are not booked in the database.
    This function will process the data in the yaml file and
    use selenium to input that data into the appropriate fields
    on the website.
    """

    driver.get(f'{base_url}?rid=30882&date={date}&start={date}%2018:30&'
               f'end={date}%2019:30')

    url_book = (f'{base_url}?rid=30882&date={date}&start={date}%'
                f'2018:30:00&end={date}%2019:30:00')

    url_res = (f'{base_url}?rid=30882&date={date}&start={date}%'
               f'2018:30:00&end={date}%2019:30:00&waitlist=1')

    if 'platser kvar' in driver.page_source:
        url = url_book
    else:
        url = url_res

    driver.get(url)

    with open(patrons_file, 'r') as stream:
        entries = yaml.load(stream)

        for entry in entries:
            name = entries[entry]['fnamn']
            surname = entries[entry]['enamn']
            mobile = entries[entry]['mobil']
            email = entries[entry]['email']

            WebDriverWait(driver, 10).until(
                ec.presence_of_element_located((By.NAME, 'fnamn')))
            elem = driver.find_element_by_name('fnamn')
            elem.send_keys(name)
            elem = driver.find_element_by_name('enamn')
            elem.send_keys(surname)
            elem = driver.find_element_by_name('a2')
            elem.send_keys(mobile)
            elem = driver.find_element_by_name('a1')
            elem.send_keys(email)

            remember_me = driver.find_element_by_id('spara2')
            if remember_me.is_selected():
                driver.execute_script("arguments[0].click();", remember_me)
            else:
                pass

            submit = driver.find_element_by_id('confirm_button')
            driver.execute_script("arguments[0].click();", submit)
            driver.execute_script("window.history.go(-1)")

            logger.info('Successfully booked ' + name + ' in for ' + date)


def teardown(driver):
    driver.quit()


if __name__ == '__main__':
    main()
