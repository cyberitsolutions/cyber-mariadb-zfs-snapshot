::

    /connect irc.libera.chat
    /join #maria
    17:21 <twb> With super basic "mysqldump ⋯ >backup.sql" combined with ZFS snapshots, the backup.sql dataset gets quite large because ZFS can't (efficiently) de-duplicate content that in unchanged between .sql files.
    17:22 <twb> Long ago, when I was last poking at this, I vaguely remember a way to say "hey, mariadb, please be quiescent for the next 30 seconds"
    17:22 <twb> During which time you make an ordinary zfs snapshot of /var/lib/mysql, and hooray, that's it, you're done
    17:22 <twb> Did I dream that, or is it A Thing?  I can't see it on https://mariadb.com/kb/en/backup-and-restore-overview/
    17:23 <twb> Ah wait it's under "filesystem snapshots".  I was looking for "quiescent"

Prior art:

* https://packages.debian.org/sid/mylvmbackup
* https://github.com/cyberitsolutions/cyber-zfs-backup

  We will not do any send/recv here; we will leave that to cyber-zfs-backup.
  Arguably this script should be part of cyber-zfs-backup, but
  I fucking hate mysql, so let's keep it separate for now.

OK so the basic process is:

1. open a connection to MySQL (and keep it open!)
2. open a cursor and a transaction, I guess, for good measure.
3. issue ``FLUSH TABLES WITH READ LOCK``

   UPDATE::

      <montywi> twb, note that in later MariaDB, you can do better than FLUSH TABLES WITH READ LOCK. See https://mariadb.com/kb/en/backup-stage/#using-backup-stage-commands-with-storage-snapshots
      <montywi> twb, and also https://mariadb.com/kb/en/storage-snapshots-and-backup-stage-commands/

4. run ``zfs snapshot create <something>/var/lib/mysql@<my cool app>-<unix timestamp>``
5. close the MySQL connection

6. to avoid hitting snapshot_limit_, expire old snapshots.  Do we care about multiple rotations, or just "keep the last `n` snaps"?

The setup that happens before this is obviously:

* do everything in here: https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Workload%20Tuning.html#mysql
* create a system user that this will run as
* use zfs-allow_ to grant that user permission to ``zfs snapshot`` and ``zfs destroy`` for the `something`/var/lib/mysql tree.
* *need* some way to specify what `something` is.  Config file, or just patch the systemd unit?
* *want* some way to configure retention policy, in case "just always keep the last 7 snapshots" is too many/few.
* ``zfs allow`` is by UID, not by username.  Therefore we would really like to either have a consistent ID.  Otherwise if we send/recv, then restore, in some cases the ID won't match, and weirdness will ensure.

  Could we run systemd with ``DynamicUser=yes`` and then use privileged ``ExecStartPre=+zfs allow ⋯`` and ``ExecStartPost=+zfs unallow`` to allow it on the fly?  Is that crazy?  It's very clean, BUT it would leave a mess if the main script (``ExecStart=mariadb-zfs-snapshot``) crashed, right?

  ::

     /connect irc.libera.chat
     /join #systemd
     17:46 <twb> OK so I have a crazy idea
     17:47 <twb> in ZFS you can say "sudo zfs allow" to let non-root users do things, like snapshot specific datasets
     17:48 <twb> If I make a service that has DynamicUser=yes User=my-cool-backup-user and then do ExecStartPre=+zfs allow -u my-cool-backup-user snapshot morpheus/var/lib/mysql
     17:49 <twb> ...will the privileged ExecStartPre be able to resolve that dynamic user?
     17:49 <twb> And can I write an ExecStartPost= that always runs, even if ExecStart= crashes?

.. _snapshot_limit: https://manpages.debian.org/bullseye-backports/zfsutils-linux/zfsprops.7.en.html#snapshot_limit
.. _zfs-allow: https://manpages.debian.org/bullseye-backports/zfsutils-linux/zfs-allow.8.en.html
