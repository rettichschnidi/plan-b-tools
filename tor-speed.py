#!/usr/bin/env python3
import argparse
import datetime
import re
import sys

import matplotlib.pyplot as plt
import requests
from sqlalchemy import Integer, Column, Text, DateTime, func, create_engine, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

proxies = {}

Base = declarative_base()


class ExitIp(Base):
    __tablename__ = 'exit_ip'
    id = Column(Integer, primary_key=True)
    time = Column(DateTime, default=func.now())
    ip = Column(Text)


class Speedtest(Base):
    __tablename__ = 'speed'
    id = Column(Integer, primary_key=True)
    time = Column(DateTime, default=func.now())
    url = Column(Text, nullable=False)
    duration = Column(Float)
    file_size = Column(Integer, default=0)
    bytes_per_second = Column(Float, default=0)
    http_code = Column(Integer, default=None)
    exit_ip = Column(Text)


def create_db_session(filename):
    engine = create_engine('sqlite:///' + filename)
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine
    return sessionmaker(bind=engine)()


def determine_ip(url, session):
    try:
        r = requests.get(url, timeout=20, proxies=proxies)
        if r.status_code == requests.codes.ok:
            exit_ip_entry = ExitIp(ip=r.text)
            session.add(exit_ip_entry)
            session.commit()
            return r.text.strip()
    except:
        pass
    print("Failed to determine exit ip", file=sys.stdout)
    return "unknown"


def determine_speed(url, exit_ip, session):
    speedtest_entry = Speedtest(url=url, exit_ip=exit_ip)
    begin = datetime.datetime.utcnow()
    try:
        r = requests.get(url, timeout=20, proxies=proxies)
        if r.status_code == requests.codes.ok:
            end = datetime.datetime.utcnow()
            duration = end - begin
            speedtest_entry.duration = duration.seconds + duration.microseconds / 1000000
            speedtest_entry.file_size = int(r.headers['content-length'])
            speedtest_entry.bytes_per_second = speedtest_entry.file_size / speedtest_entry.duration
            speedtest_entry.http_code = r.status_code
        else:
            raise Exception
    except Exception as e:
        print("Failed to fetch test file: {}".format(str(e)), file=sys.stdout)
    finally:
        session.add(speedtest_entry)
        session.commit()


def plot(session, ip_filter_regex, header):
    speeds = []
    ips = []

    last_speedtest = None
    for current_speedtest in session.query(Speedtest).order_by(Speedtest.time).all():
        exit_ip_str = current_speedtest.exit_ip.strip() if current_speedtest.exit_ip else ""
        if re.match(ip_filter_regex, exit_ip_str):
            speeds.append(current_speedtest.bytes_per_second)
            if not last_speedtest or last_speedtest.exit_ip != current_speedtest.exit_ip:
                ips.append(current_speedtest.exit_ip)
            else:
                ips.append("")
            last_speedtest = current_speedtest

    plt.plot(speeds, label=ip_filter_regex, marker="x")

    plt.xlabel('IP address')
    plt.ylabel('Speed [Byte/Second]')
    plt.title('Real-World-Tor-Speed: ' + header)
    plt.xticks(range(len(ips)), ips, rotation=90)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--testfile', nargs=1, metavar='<URL>', type=str,
                        help='URL to file to determine the speed of the connection.\n'
                             'E.g. https://plan-b.digitale-gesellschaft.ch/testing/testfile-10mb.img')
    parser.add_argument('--database', default='plan-b-tor-speed.db')
    parser.add_argument('--get-ip', nargs=1, metavar='<URL>', type=str,
                        help='URL to retrieve the IP address of the Tor exit node.\n"'
                             'E.g. https://plan-b.digitale-gesellschaft.ch/testing/ip.php')
    parser.add_argument('--plot', nargs=1, metavar='<ip_regex>', help="Plot collected data")
    parser.add_argument('--proxy', nargs=1, help="Proxy to use for HTTP(S).\n"
                                                 "E.g. socks5://localhost:9050")
    args = parser.parse_args()

    if not (args.testfile or args.get_ip or args.plot):
        parser.print_help()
        exit(0)

    session = create_db_session(args.database)

    ip = None
    if args.proxy:
        proxies['http'] = args.proxy[0]
        proxies['https'] = args.proxy[0]
        proxies['ftp'] = args.proxy[0]
    if args.get_ip:
        ip = determine_ip(args.get_ip[0], session)
    if args.testfile:
        determine_speed(args.testfile[0], ip, session)
    if args.plot:
        plot(session, args.plot[0], args.database)


if __name__ == '__main__':
    main()
