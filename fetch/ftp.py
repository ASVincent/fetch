"""
FTP-based retrieval of files.
"""
import ftplib
import logging
import os
import re

from . import DataSource, fetch_file


_log = logging.getLogger(__name__)


def _fetch_files(hostname,
                 target_dir,
                 reporter,
                 get_filepaths_fn,
                 override_existing=False,
                 filename_transform=None):
    """
    Fetch fetch files on the given FTP server.

    The get_filepaths_fn callback is used to get a list of files to download.

    It it passed an instance of the connection so that it can query the server if needed.

    :type get_filepaths_fn: (ftplib.FTP) -> list of str
    :type hostname: str
    :type target_dir: str
    :type reporter: FetchReporter
    """

    ftp = ftplib.FTP(hostname)
    try:
        ftp.login()

        files = get_filepaths_fn(ftp)

        for filename in files:
            _log.debug('Next filename: %r', filename)

            def ftp_fetch(t):
                """Fetch data to filename t"""
                _log.debug('Retrieving %r to %r', filename, t)
                with open(t, 'wb') as f:
                    ftp.retrbinary('RETR ' + filename, f.write)

            fetch_file(
                'ftp://%s%s' % (hostname, filename),
                ftp_fetch,
                reporter,
                os.path.basename(filename),
                target_dir,
                filename_transform=filename_transform,
                override_existing=override_existing
            )
    finally:
        ftp.quit()


class FtpSource(DataSource):
    """
    Download specific files from FTP.

    This is useful for unchanging URLs that need to be
    repeatedly updated.
    """

    def __init__(self, hostname, paths, target_dir, filename_transform=None):
        """
        :type paths: list of str
        :type target_dir: str
        :return:
        """
        super(FtpSource, self).__init__()

        self.hostname = hostname
        self.paths = paths
        self.target_dir = target_dir
        self.filename_transform = filename_transform

    def trigger(self, reporter):
        """
        Download all files, overriding existing.
        :type reporter: FetchReporter
        :return:
        """

        def get_files(_):
            """Return a static set of file paths to download"""
            return self.paths

        _fetch_files(
            self.hostname,
            self.target_dir,
            reporter,
            get_files,
            override_existing=True,
            filename_transform=self.filename_transform
        )


class FtpListingSource(DataSource):
    """
    Download files matching a pattern in an FTP directory.
    """

    def __init__(self, hostname, source_dir, name_pattern, target_dir):
        """
        :type source_urls: list of str
        :type target_dir: str
        :return:
        """
        super(FtpListingSource, self).__init__()

        self.hostname = hostname
        self.source_dir = source_dir
        self.name_pattern = name_pattern
        self.target_dir = target_dir

    def trigger(self, reporter):
        """
        Download all matching files.

        :type reporter: FetchReporter
        :return:
        """

        def get_files(ftp):
            """Get files that match the name_pattern in the target directory."""
            try:
                files = ftp.nlst(self.source_dir)
            except ftplib.error_perm as resp:
                if str(resp) == "550 No files found":
                    _log.info("No files in remote directory")
                    files = []
                else:
                    raise
            except ftplib.error_temp as resp:
                if str(resp).strip().startswith('450'):
                    _log.info("No remote directory")
                    files = []
                else:
                    raise

            _log.debug('File list of length %r', len(files))
            files = [
                os.path.join(self.source_dir, f)
                for f in files if re.match(self.name_pattern, os.path.basename(f))
            ]
            _log.debug('Filtered list of length %r', len(files))
            return files

        _fetch_files(
            self.hostname,
            self.target_dir,
            reporter,
            get_files,
            override_existing=True
        )
