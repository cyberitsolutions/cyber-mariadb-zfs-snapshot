#!/usr/bin/python3
import argparse
import contextlib
import datetime
import json
import logging
import subprocess

import MySQLdb                  # https://mysqlclient.readthedocs.io/


__doc__ = """ like mylvmbackup but ZFS (not LVM) """
__version__ = '0.1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset',
        help='What to snapshot (e.g. rpool/ROOT/var/lib/mysql)',
        **guess_dataset())
    parser.set_defaults(
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
def lock_database():
    with contextlib.closing(MySQLdb._mysql.connect()) as conn:
        # FIXME: this API doesn't have cursors AT ALL???
        # FIXME: this API doesn't have with/as for clean transaction commit/rollback???
        # THIS IS NOT CONFORMANT TO https://peps.python.org/pep-0249 AT FUCKING ALL.
        conn.query('FLUSH TABLES WITH READ LOCK')
        if (result := conn.store_result()) is not None:
            raise RuntimeError('Something fucky happened', result)
        yield
        conn.query('UNLOCK TABLES')
        if (result := conn.store_result()) is not None:
            raise RuntimeError('Something fucky happened', result)


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


def guess_dataset():
    try:
        stdout = subprocess.check_output(
            ['findmnt',
             '--json',
             '--type=zfs',
             '--output=source',
             '--mountpoint=/var/lib/mysql'])
        dataset = json.loads(stdout)['filesystems'][0]['source']
        return {'required': False, 'default': dataset}
    except:                     # NOQA: E722
        return {'required': True}  # no guess -- you must be explicit
