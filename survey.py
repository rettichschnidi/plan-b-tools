#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys

import matplotlib.pyplot as plt
from sqlalchemy import Integer, Column, Text, DateTime, func, ForeignKey, String, create_engine, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class Scan(Base):
    __tablename__ = 'scan'
    id = Column(Integer, primary_key=True)
    description = Column(Text, nullable=False)
    time = Column(DateTime, default=func.now())
    data = Column(Text, nullable=False)


class Result(Base):
    __tablename__ = 'result'
    scan_id = Column(ForeignKey(Scan.id), primary_key=True)
    mac = Column(String(17), nullable=False, primary_key=True)
    essid = Column(String(32), nullable=False)
    quality = Column(Float, nullable=False)
    signal_level = Column(Text, nullable=False)
    frequency = Column(Text, nullable=False)
    channel = Column(Integer, nullable=False)

    scan = relationship(Scan)


def scan(interface, description, session):
    result = subprocess.run(['sudo', 'iwlist', interface, 'scan'], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.stderr:
        print(result.stderr.decode('utf-8'), file=sys.stderr)
    if result.stderr or result.returncode:
        exit(-1)

    result_entry = Scan(description=description, data=result.stdout.decode('utf-8'))
    session.add(result_entry)
    session.commit()
    return result_entry


def create_db_session(filename):
    engine = create_engine('sqlite:///' + filename)
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine
    return sessionmaker(bind=engine)()


def analyze(scan_object, session):
    assert scan_object.data

    current_result = None
    for line in scan_object.data.splitlines():
        line = line.strip()
        m = re.match(r'^Cell \d+ - Address: (?P<mac>.+)', line)
        if m:
            assert current_result is None
            current_result = Result(scan_id=scan_object.id, mac=m.group('mac'))
            continue

        m = re.match(r"Frequency:(?P<frequency>.+) GHz \(Channel (?P<channel>\d+)\)$", line)
        if m:
            current_result.frequency = m.group('frequency')
            current_result.channel = m.group('channel')
            continue

        m = re.match(
            r"Quality=(?P<quality_nominator>\d+)/(?P<quality_denominator>\d+)  Signal level=(?P<signal_level>.+) dBm$",
            line)
        if m:
            current_result.quality = int(m.group('quality_nominator')) / int(m.group('quality_denominator'))
            current_result.signal_level = m.group('signal_level')
            continue

        m = re.match(r"ESSID:\"(?P<essid>.+)\"", line)
        if m:
            current_result.essid = m.group('essid')
            session.add(current_result)
            current_result = None

    session.commit()


def plot(session, filter_regex):
    networks = {}
    scans = session.query(Scan).all()
    scan_count = len(scans)
    for unique_ssid_results in session.query(Result.essid).distinct():
        networks[unique_ssid_results.essid] = [0 for x in range(scan_count)]

    for index, scan in enumerate(session.query(Scan).all()):
        # print("Scan '{}' at {}:".format(scan.description, scan.time))
        for result in session.query(Result).filter(Result.scan == scan):
            networks[result.essid][index] = result.quality
            # print(" {}: {}".format(result.essid, result.quality))

    fig, ax = plt.subplots(figsize=(20, 10))
    for essid, value in networks.items():
        if re.match(filter_regex, essid):
            plt.plot(value, label=essid, marker="x")

    plt.xlabel('Location/Time')
    plt.ylabel('Quality')
    plt.title('Quality vs Locality')
    plt.xticks(range(scan_count), [x.description + "\n" + str(x.time) for x in scans], rotation=90)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan', nargs=2, metavar=('<interface>', '<description>'))
    parser.add_argument('--database', default='plan-b-survey.db')
    parser.add_argument('--plot', nargs=1, metavar=('<network_regex>'),
                        help="Plot specified networks ('.*' for all)")
    args = parser.parse_args()

    if not (args.scan or args.plot):
        parser.print_help()
        exit(0)

    session = create_db_session(args.database)

    if args.scan:
        scan_object = scan(args.scan[0], args.scan[1], session)
        analyze(scan_object, session)

    if args.plot:
        plot(session, args.plot[0])


if __name__ == '__main__':
    main()
