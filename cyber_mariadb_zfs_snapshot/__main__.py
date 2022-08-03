#!/usr/bin/python3
import argparse
import contextlib
import datetime
import logging
import subprocess

import MySQLdb                  # https://mysqlclient.readthedocs.io/


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'dataset',
        help='What to snapshot (e.g. rpool/var/lib/mysql)')
    parser.add_defaults(
        snapshot_prefix='cyber_mariadb_zfs_snapshot',
        timestamp=int(datetime.datetime.now().timestamp()))
    args = parser.parse_args()
    with lock_database():
        snapshot(args)
    expire(args)


def snapshot(args):
    subprocess.check_call([
        '/sbin/zfs', 'snapshot', '-r',
        f'{args.dataset}@{args.snapshot_prefix}_{args.timestamp}'])


# https://mariadb.com/kb/en/backup-and-restore-overview/#filesystem-snapshots
@contextlib.contextmanager
def lock_database(args):
    with MySQLdb._mysql.connect() as conn:
        with conn.cursor() as cursor:
            with cursor:        # transaction
                cursor.execute('FLUSH TABLES WITH READ LOCK')
                yield
                cursor.execute('UNLOCK TABLES')


def expire(args):
    """for now, just keep the last 10 snapshots, the end."""
    # All snapshot names, non-recursive, order by creation time (oldest first).
    snapshots = subprocess.check_output(
        ['/sbin/zfs', 'list', args.dataset,
         '-prd1', '-tsnapshot', '-screation', '-oname'],
        text=True).splitlines()
    # Only OUR snapshots.
    snapshots = [
        s.partition('@')[2]
        for s in snapshots
        if s.startswith(f'{args.dataset}@{args.snapshot_prefix}_')]
    # Swap to newest first.
    snapshots.reverse()
    # Keep the last 10.
    snapshots_to_expire = snapshots[10:]

    if not snapshots_to_expire:
        logging.debug('No snapshots to expire')
        return
    else:
        logging.debug('Expiring %s', snapshots_to_expire)
        subprocess.check_call([
            '/sbin/zfs', 'destroy', '-r',
            f'{args.dataset}@{",".join(snapshots_to_expire)}'])


if __name__ == '__main__':
    main()
