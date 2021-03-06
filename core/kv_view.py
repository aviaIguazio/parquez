from datetime import datetime, timedelta
import re
from pyhive import presto
from dateutil.relativedelta import relativedelta

PARTITION_INTERVAL_RE = r"([0-9]+)([a-zA-Z]+)"


# TODO: Add verification that hive table created (handle Trying to send on a closed client exception


class KVView(object):
    def __init__(self, logger, real_time_window, conf, kv_table):
        self.logger = logger
        self.kv_table = kv_table
        self.name = kv_table.name + "_view"
        self.real_time_window = real_time_window
        self.conf = conf
        self.uri = conf.presto_uri
        self.cursor = None

    def connect(self):
        req_kw = {'auth': (self.conf.username, self.conf.v3io_access_key), 'verify': False}
        self.cursor = presto.connect(self.uri, port=443, username=self.conf.username,
                                     protocol='https', requests_kwargs=req_kw).cursor()
        self.logger.info("connected to presto")

    def disconnect(self):
        self.cursor.close()

    def execute_command(self, command):
        self.cursor.execute(command)

    def parse_real_time_window(self):
        now = datetime.utcnow()
        part = re.match(PARTITION_INTERVAL_RE, self.real_time_window).group(2)
        val = int(re.match(PARTITION_INTERVAL_RE, self.real_time_window).group(1))
        self.logger.debug("generate time window".format(part))
        if part == 'd':
            window_time = now - timedelta(days=val - 1)
        if part == 'h':
            window_time = now - timedelta(hours=val - 1)
        if part == 'M':
            window_time = now - relativedelta(months=val - 1)
        self.logger.info("window Time " + str(window_time))
        return window_time

    # def generate_where_clause(self):
    #     window_time = self.parse_real_time_window()
    #     part = re.match(PARTITION_INTERVAL_RE, self.real_time_window).group(2)
    #     self.logger.debug("generate_partition_by {0}".format(part))
    #     condition = ''
    #     if part == 'y':
    #         condition += "year>=" + str(window_time.year)
    #     if part == 'M':
    #         condition += "year>=" + str(window_time.year) + " AND month>=" + str(window_time.month)
    #     if part == 'd':
    #         condition += "year>=" + str(window_time.year) + " AND month>=" + str(window_time.month) + " AND day>=" \
    #                      + str(window_time.day)
    #     if part == 'h':
    #         condition += "year>=" + str(window_time.year) + " AND month>=" + str(window_time.month) + " AND day>=" + \
    #                      str(window_time.day) + " AND hour>=" + str(window_time.hour)
    #     clause = " WHERE " + condition
    #     return clause

    def generate_calculated_filter_clause(self):
        window_time = self.parse_real_time_window()
        part = re.match(PARTITION_INTERVAL_RE, self.real_time_window).group(2)
        self.logger.debug("generate_partition_by {0}".format(part))
        now = datetime.utcnow()
        clause = self.where_clause_filter(now, window_time, part)
        return clause

    def create_view_prefix(self):
        hive_prefix = "hive." + self.conf.hive_schema + "."
        v3io_prefix = "v3io." + self.conf.v3io_container + "."
        prefix = "CREATE OR REPLACE VIEW " + hive_prefix + self.kv_table.name + \
                 "_view AS SELECT * FROM " + v3io_prefix + self.kv_table.name
        return prefix

    def create_view(self, command):
        self.logger.debug("Create view command : " + command)
        self.connect()
        self.logger.info(command)
        self.execute_command(command)
        self.cursor.fetchone()
        self.disconnect()

    def generate_crete_view_script(self):
        try:
            self.logger.debug("generating kv view script")
            prefix = self.create_view_prefix()
            # clause = self.generate_where_clause()
            clause = self.generate_calculated_filter_clause()
            script = prefix + clause
            self.logger.debug("create kv view script {}".format(script))
            self.create_view(script)
        except Exception as e:
            self.logger.error(e)
            raise

    def where_clause_filter(self, start_date, end_date, partition_by):
        start_date_year = start_date.year
        start_date_month = start_date.month
        end_date_year = end_date.year
        end_date_month = end_date.month
        end_date_day = end_date.day

        clause_suffix = ""

        if partition_by == 'y':
            if start_date.year != end_date_year:
                clause_suffix += ''.join([" year >=", str(end_date_year)])
            else:
                clause_suffix += "year>=" + str(end_date_year)

        if partition_by == 'M':
            if start_date.year != end_date_year:
                clause_suffix += ''.join(["(year >=", str(start_date_year), ")"])
                clause_suffix += " or "
                clause_suffix += ''.join(["(year >=", str(end_date_year), " and month>=", str(end_date_month)])
            else:
                clause_suffix += "year>=" + str(end_date_year) + " AND month>=" + str(end_date_month)

        if partition_by == 'd':
            if start_date.year != end_date_year:
                clause_suffix += ''.join(["( year >=", str(start_date_year), ")"])
                clause_suffix += " or "
                clause_suffix += ''.join(
                    ["(year >=", str(end_date_year), " and month>=", str(end_date_month), " and day>=",
                     str(end_date_day), ")"])
            else:
                if start_date_month != end_date_month:
                    clause_suffix += ''.join(
                        ["( year >=", str(start_date_year), " and month>=", str(start_date_month), ")"])
                    clause_suffix += " or "
                    clause_suffix += ''.join(
                        ["(year >=", str(end_date_year), " and month>=", str(end_date_month), " and day>=",
                         str(end_date_day), ")"])
                else:
                    clause_suffix += "year>=" + str(end_date_year) + " AND month>=" + str(
                        end_date_month) + " AND day>=" \
                                 + str(end_date_day)

        if partition_by == 'h':
            clause_suffix += "year>=" + str(end_date_year) + " AND month>=" + str(end_date_month) + " AND day>=" + \
                         str(end_date_day) + " AND hour>=" + str(end_date.hour)
        clause_suffix = " WHERE " + clause_suffix
        self.logger.info(clause_suffix)
        return clause_suffix
