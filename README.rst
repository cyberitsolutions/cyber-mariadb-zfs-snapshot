::

    /connect irc.libera.chat
    /join #maria
    17:21 <twb> With super basic "mysqldump ⋯ >backup.sql" combined with ZFS snapshots, the backup.sql dataset gets quite large because ZFS can't (efficiently) de-duplicate content that in unchanged between .sql files.
    17:22 <twb> Long ago, when I was last poking at this, I vaguely remember a way to say "hey, mariadb, please be quiescent for the next 30 seconds"
    17:22 <twb> During which time you make an ordinary zfs snapshot of /var/lib/mysql, and hooray, that's it, you're done
    17:22 <twb> Did I dream that, or is it A Thing?  I can't see it on https://mariadb.com/kb/en/backup-and-restore-overview/
    17:23 <twb> Ah wait it's under "filesystem snapshots".  I was looking for "quiescent"
