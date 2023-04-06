"""
=== Module Description ===

This file contains the WasteWrangler class and some simple testing functions.
"""

import datetime as dt
import psycopg2 as pg
import psycopg2.extensions as pg_ext
import psycopg2.extras as pg_extras
from typing import Optional, TextIO


class WasteWrangler:
    """A class that can work with data conforming to the schema in
    waste_wrangler_schema.ddl.

    === Instance Attributes ===
    connection: connection to a PostgreSQL database of a waste management
    service.

    Representation invariants:
    - The database to which connection is established conforms to the schema
      in waste_wrangler_schema.ddl.
    """
    connection: Optional[pg_ext.connection]

    def __init__(self) -> None:
        """Initialize this WasteWrangler instance, with no database connection
        yet.
        """
        self.connection = None

    def connect(self, dbname: str, username: str, password: str) -> bool:
        """Establish a connection to the database <dbname> using the
        username <username> and password <password>, and assign it to the
        instance attribute <connection>. In addition, set the search path
        to waste_wrangler.

        Return True if the connection was made successfully, False otherwise.
        I.e., do NOT throw an error if making the connection fails.

        >>> ww = WasteWrangler()
        >>> ww.connect("csc343h-marinat", "marinat", "")
        True
        >>> # In this example, the connection cannot be made.
        >>> ww.connect("invalid", "nonsense", "incorrect")
        False
        """
        try:
            self.connection = pg.connect(
                dbname=dbname, user=username, password=password,
                options="-c search_path=waste_wrangler"
            )
            return True
        except pg.Error:
            return False

    def disconnect(self) -> bool:
        """Close this WasteWrangler's connection to the database.

        Return True if closing the connection was successful, False otherwise.
        I.e., do NOT throw an error if closing the connection failed.

        >>> ww = WasteWrangler()
        >>> ww.connect("csc343h-marinat", "marinat", "")
        True
        >>> ww.disconnect()
        True
        """
        try:
            if self.connection and not self.connection.closed:
                self.connection.close()
            return True
        except pg.Error:
            return False


    def schedule_trip(self, rid: int, time: dt.datetime) -> bool:
        """Schedule a truck and two employees to the route identified
        with <rid> at the given time stamp <time> to pick up an
        unknown volume of waste, and deliver it to the appropriate facility.

        The employees and truck selected for this trip must be available:
            * They can NOT be scheduled for a different trip from 30 minutes
              of the expected start until 30 minutes after the end time of this
              trip.
            * The truck can NOT be scheduled for maintenance on the same day.

        The end time of a trip can be computed by assuming that all trucks
        travel at an average of 5 kph.

        From the available trucks, pick a truck that can carry the same
        waste type as <rid> and give priority based on larger capacity and
        use the ascending order of ids to break ties.

        From the available employees, give preference based on hireDate
        (employees who have the most experience get priority), and order by
        ascending order of ids in case of ties, such that at least one
        employee can drive the truck type of the selected truck.

        Pick a facility that has the same waste type a <rid> and select the one
        with the lowest fID.

        Return True iff a trip has been scheduled successfully for the given
            route.
        This method should NOT throw an error i.e. if scheduling fails, the
        method should simply return False.

        No changes should be made to the database if scheduling the trip fails.

        Scheduling fails i.e., the method returns False, if any of the following
        is true:
            * If rid is an invalid route ID.
            * If no appropriate truck, drivers or facility can be found.
            * If a trip has already been scheduled for <rid> on the same day
              as <time> (that encompasses the exact same time as <time>).
            * If the trip can't be scheduled within working hours i.e., between
              8:00-16:00.

        While a realistic use case will provide a <time> in the near future, our
        tests could use any valid value for <time>.
        """
        try:
            cur = self.connection.cursor()

            # check 1
            cur.execute("SELECT rid FROM route WHERE rid = %s;", (rid,))
            if cur.rowcount == 0:
                self.connection.rollback()
                cur.close()
                return False

            #get trip end time
            cur.execute("SELECT length FROM route WHERE rid = %s;", (rid,))
            trip_hrs = cur.fetchone()[0] / 5
            cur.execute("SELECT %s::timestamp + interval '%s hour';", (time, trip_hrs))
            trip_end = cur.fetchone()[0]

            # check 4
            if time < time.replace(hour=8, minute=0, second=0) \
                or time > time.replace(hour=16, minute=0, second=0) \
                or trip_end > time.replace(hour=16, minute=0, second=0):
                self.connection.rollback()
                cur.close()
                return False

            # check 3
            cur.execute("SELECT ttime::date - %s::date FROM trip WHERE rid = %s;", (time, rid))
            for timediff in cur:
                if timediff[0] == 0:
                    self.connection.rollback()
                    cur.close()
                    return False

            #find best facility
            cur.execute("SELECT fid FROM route NATURAL JOIN facility \
                WHERE rid = %s ORDER BY fid;", (rid,))
            if cur.rowcount == 0:
                self.connection.rollback()
                cur.close()
                return False
            else:
                best_f = cur.fetchone()[0]

            query = ''' CREATE VIEW notAval AS
                        SELECT *
                        FROM (trip NATURAL JOIN route) t1
                        WHERE 't' = (SELECT (%s::timestamp - interval '0.5 hour',
                                           %s::timestamp + interval '0.5 hour') OVERLAPS
                                           (t1.ttime::timestamp, (t1.ttime::timestamp + length / 5 * interval '1 hour')));

                        CREATE VIEW availableEmployees AS
                        SELECT *
                        FROM driver
                        WHERE eid NOT IN (
                        SELECT eid1
                        FROM notAval) AND eid NOT IN (
                        SELECT eid2
                        FROM notAval);

                        CREATE VIEW availableTrucks AS
                        SELECT *
                        FROM truck
                        WHERE tid NOT IN (
                        SELECT tid
                        FROM notAval) AND tid NOT IN (
                        SELECT tid
                        FROM maintenance
                        WHERE mdate::date - %s::date = 0);
                    '''
            cur.execute(query, (time, trip_end, time))

            # find best truck among available truck
            query = '''(SELECT tid, trucktype, capacity FROM truck
                        WHERE tid IN (SELECT tid FROM availableTrucks))
                        INTERSECT (
                        SELECT tid, trucktype, capacity
                        FROM truck JOIN trucktype USING (trucktype)
                        JOIN route USING (wastetype)
                        WHERE rid = %s)
                        ORDER BY capacity DESC, tid;
                    '''
            cur.execute(query, (rid,))
            if cur.rowcount == 0:
                self.connection.rollback()
                cur.close()
                return False
            else:
                best_truck = cur.fetchone() #(tid, trucktype, capacity)

                #find best 2 employees, 1st one no restrict on trucktype
                query = '''SELECT employee.eid, trucktype 
                            FROM availableEmployees NATURAL JOIN employee 
                            ORDER BY hiredate, employee.eid;             
                        '''
                cur.execute(query)
                if cur.rowcount == 0:
                    cur.execute("DROP VIEW IF EXISTS notAval, availableTrucks, availableEmployees;")
                    self.connection.rollback()
                    cur.close()
                    return False
                else:
                    best_e_one = cur.fetchone() #(eid, trucktype)
                    if best_e_one[1] == best_truck[1]: # if first best eid happens to drive trucktype
                        best_e_two = cur.fetchone()
                    else:
                        # otherwise 2nd eid has to be able to drive the trucktype
                        best_e_two = None
                        tup = cur.fetchone() # 2nd eid in list
                        not_found = True
                        while tup is not None and not_found:
                            if tup[1] == best_truck[1] and tup[0] != best_e_one[0]:
                                best_e_two = tup
                                not_found = False
                            tup = cur.fetchone()

                        if best_e_two is None: # if reach end of the list and no one can drive trucktype
                            cur.execute("DROP VIEW IF EXISTS notAval, availableTrucks, availableEmployees;")
                            self.connection.rollback()
                            cur.close()
                            return False

            cur.execute("INSERT INTO trip VALUES (%s, %s, %s, NULL, %s, %s, %s);", \
                (rid, best_truck[0], time, max(best_e_one[0], best_e_two[0]), 
                min(best_e_one[0], best_e_two[0]), best_f))

            cur.execute("DROP VIEW IF EXISTS notAval, availableTrucks, availableEmployees;")
            self.connection.commit()
            cur.close()

            return True

        except pg.Error as ex:
            # You may find it helpful to uncomment this line while debugging,
            # as it will show you all the details of the error that occurred:
            # raise ex
            return False

    def schedule_trips(self, tid: int, date: dt.date) -> int:
        """Schedule the truck identified with <tid> for trips on <date> using
        the following approach:

            1. Find routes not already scheduled for <date>, for which <tid>
               is able to carry the waste type. Schedule these by ascending
               order of rIDs.

            2. Starting from 8 a.m., find the earliest available pair
               of drivers who are available all day. Give preference
               based on hireDate (employees who have the most
               experience get priority), and break ties by choosing
               the lower eID, such that at least one employee can
               drive the truck type of <tid>.

               The facility for the trip is the one with the lowest fID that can
               handle the waste type of the route.

               The volume for the scheduled trip should be null.

            3. Continue scheduling, making sure to leave 30 minutes between
               the end of one trip and the start of the next, using the
               assumption that <tid> will travel an average of 5 kph.
               Make sure that the last trip will not end after 4 p.m.

        Return the number of trips that were scheduled successfully.

        Your method should NOT raise an error.

        While a realistic use case will provide a <date> in the near future, our
        tests could use any valid value for <date>.
        """
        try:
            
            cur = self.connection.cursor()

            cur.execute("SELECT trucktype, wastetype \
                        FROM trucktype JOIN truck USING (trucktype) \
                        WHERE %s = tid;", (tid,))

            if cur.rowcount == 0:
                self.connection.rollback()
                cur.close()
                return 0
            
            target_truck = cur.fetchone() # 0 = trucktype, 1 = wastetype

            # part 1
            query = '''SELECT DISTINCT rid, length
                        FROM route
                        WHERE wastetype = %s AND 
                                rid NOT IN (
                                        SELECT rid FROM trip
                                        WHERE ttime::date - %s::date = 0)
                        ORDER BY rid;
                    '''
            cur.execute(query, (target_truck[1], date))

            if cur.rowcount == 0:
                self.connection.rollback()
                cur.close()
                return 0
            
            aval_route = cur.fetchall()

            # part 2
            query = '''CREATE VIEW AvalDriver AS (
                        (SELECT eid FROM driver)
                        EXCEPT
                        (SELECT eid1 AS eid
                        FROM trip
                        WHERE ttime::date - %s::date = 0)
                        EXCEPT
                        (SELECT eid2 AS eid
                        FROM trip
                        WHERE ttime::date - %s::date = 0));

                        SELECT DISTINCT eid, trucktype, hiredate
                        FROM driver JOIN employee USING (eid)
                        WHERE eid IN (SELECT eid FROM AvalDriver)
                        ORDER BY hiredate, eid;
                    '''
            cur.execute(query, (date, date))
            if cur.rowcount < 2:
                cur.execute("DROP VIEW IF EXISTS AvalDriver;")
                self.connection.rollback()
                cur.close()
                return 0

            d_one = cur.fetchone() # (eid, trucktype)
            d_two = None
            if d_one[1] == target_truck[0]:
                d_two = cur.fetchone()
            else:
                tup = cur.fetchone()
                not_found = True
                while tup is not None and not_found:
                    if tup[1] == target_truck[0] and tup[0] != d_one[0]:
                        d_two = tup
                        not_found = False
                    tup = cur.fetchone()
                if d_two is None:
                    cur.execute("DROP VIEW IF EXISTS AvalDriver;")
                    self.connection.rollback()
                    cur.close()
                    return 0
            
            query = '''SELECT fid
                        FROM facility
                        WHERE wastetype = %s
                        ORDER BY fid;
                    '''

            cur.execute(query, (target_truck[1],))

            if cur.rowcount == 0:
                cur.execute("DROP VIEW IF EXISTS AvalDriver;")
                self.connection.rollback()
                cur.close()
                return 0
            
            fid = cur.fetchone()[0]
            
            # part 3
            route_hrs = []
            for route in aval_route:
                route_hrs.append((route[0], route[1] / 5)) # (rid, hrs)
            
            working_hrs = True
            i = 0
            start_time = dt.datetime.combine(date, dt.time(8, 0))
            off_time = dt.datetime.combine(date, dt.time(16, 0))
            while working_hrs and i < len(route_hrs):
                # end time of trip i
                cur.execute("SELECT %s::timestamp + interval '%s hour';", (start_time, route_hrs[i][1]))
                end_time = cur.fetchone()[0]
                # if end_time is within working hrs, insert
                if end_time < off_time: 
                    cur.execute("INSERT INTO trip VALUES (%s, %s, %s, NULL, %s, %s, %s);", \
                                (route_hrs[i][0], tid, start_time, max(d_one[0], d_two[0]), min(d_one[0], d_two[0]), fid))
                else:
                    working_hrs = False
                
                # start time of trip i + 1
                cur.execute("SELECT %s::timestamp + interval '0.5 hour';", (end_time,))
                start_time = cur.fetchone()[0]

                i += 1

            self.connection.commit()
            cur.close()

            return i

        except pg.Error as ex:
            # raise ex
            return False


    def update_technicians(self, qualifications_file: TextIO) -> int:
        """Given the open file <qualifications_file> that follows the format
        described on the handout, update the database to reflect that the
        recorded technicians can now work on the corresponding given truck type.

        For the purposes of this method, you may assume that no two employees
        in our database have the same name i.e., an employee can be uniquely
        identified using their name.

        Your method should NOT throw an error.
        Instead, only correct entries should be reflected in the database.
        Return the number of successful changes, which is the same as the number
        of valid entries.
        Invalid entries include:
            * Incorrect employee name.
            * Incorrect truck type.
            * The technician is already recorded to work on the corresponding
              truck type.
            * The employee is a driver.

        Hint: We have provided a helper _read_qualifications_file that you
            might find helpful for completing this method.
        """
        try:
            cur = self.connection.cursor()

            content = self._read_qualifications_file(qualifications_file)
            # [[first name, last name, trucktype]]

            valid_entries = 0

            for input in content:
                valid = True

                #check correct trucktype
                cur.execute("SELECT * FROM trucktype WHERE trucktype = %s;", (input[2],))
                if cur.rowcount < 1:
                    valid = False

                # check correct employee name
                name = input[0] + ' ' + input[1]
                cur.execute("SELECT eid FROM employee WHERE name = %s;", (name,))
                if cur.rowcount < 1:
                    valid = False
                else:
                    eid = cur.fetchone()[0]

                    # check already recorded pairs
                    cur.execute("SELECT * FROM technician WHERE eid = %s AND trucktype = %s;", (eid, input[2]))
                    if cur.rowcount > 0:
                        valid = False
                    
                    # check if employee is a driver
                    cur.execute("SELECT * FROM driver WHERE eid = %s;", (eid,))
                    if cur.rowcount > 0:
                        valid = False
                
                if valid:
                    cur.execute("INSERT INTO technician VALUES (%s, %s);", (eid, input[2]))
                    valid_entries += 1
            
            self.connection.commit()
            cur.close()

            return valid_entries

        except pg.Error as ex:
            # You may find it helpful to uncomment this line while debugging,
            # as it will show you all the details of the error that occurred:
            # raise ex
            return 0

    def workmate_sphere(self, eid: int) -> list[int]:
        """Return the workmate sphere of the driver identified by <eid>, as a
        list of eIDs.

        The workmate sphere of <eid> is:
            * Any employee who has been on a trip with <eid>.
            * Recursively, any employee who has been on a trip with an employee
              in <eid>'s workmate sphere is also in <eid>'s workmate sphere.

        The returned list should NOT include <eid> and should NOT include
        duplicates.

        The order of the returned ids does NOT matter.

        Your method should NOT return an error. If an error occurs, your method
        should simply return an empty list.
        """
        try:
            cur = self.connection.cursor()

            # check valid eid
            cur.execute("SELECT * FROM driver WHERE eid = %s;", (eid, ))
            if cur.rowcount < 1:
                self.connection.rollback()
                cur.close()
                return []
            
            # get first layer in result
            query = ''' (SELECT eid1 FROM trip WHERE eid2 = %s)
                        UNION
                        (SELECT eid2 FROM trip WHERE eid1 = %s);
                    '''
            cur.execute(query, (eid, eid))
            if cur.rowcount < 1:
                self.connection.rollback()
                cur.close()
                return []
            
            direct_workmate = cur.fetchall()
            
            result = set()
            # get & add second layer (if exists) 
            for e in direct_workmate:
                result.add(e[0]) # add first layer to result
                query = ''' (SELECT eid1 FROM trip WHERE eid2 = %s AND eid1 <> %s)
                            UNION
                            (SELECT eid2 FROM trip WHERE eid1 = %s AND eid2 <> %s);
                        '''
                cur.execute(query, (e[0], eid, e[0], eid))
                if cur.rowcount > 0:
                    for e_wm in cur:
                        result.add(e_wm[0]) # add second layer to result
            
            self.connection.commit()
            cur.close()

            return list(result)

        except pg.Error as ex:
            # You may find it helpful to uncomment this line while debugging,
            # as it will show you all the details of the error that occurred:
            # raise ex
            return []

    def schedule_maintenance(self, date: dt.date) -> int:
        """For each truck whose most recent maintenance before <date> happened
        over 90 days before <date>, and for which there is no scheduled
        maintenance up to 10 days following date, schedule maintenance with
        a technician qualified to work on that truck in ascending order of tIDs.

        For example, if <date> is 2023-05-02, then you should consider trucks
        that had maintenance before 2023-02-01, and for which there is no
        scheduled maintenance from 2023-05-02 to 2023-05-12 inclusive.

        Choose the first day after <date> when there is a qualified technician
        available (not scheduled to maintain another truck that day) and the
        truck is not scheduled for a trip or maintenance on that day.

        If there is more than one technician available on a given day, choose
        the one with the lowest eID.

        Return the number of trucks that were successfully scheduled for
        maintenance.

        Your method should NOT throw an error.

        While a realistic use case will provide a <date> in the near future, our
        tests could use any valid value for <date>.
        """
        try:
            cur = self.connection.cursor()

            # select tid that need maintenance
            query = ''' (SELECT tid FROM maintenance)
                        EXCEPT 
                        (SELECT tid FROM maintenance
                        WHERE %s::date - mdate::date <= 90)
                        EXCEPT
                        (SELECT tid FROM maintenance
                        WHERE mdate::date - %s::date <= 10 AND mdate::date - %s::date > 0);
                    '''
            cur.execute(query, (date, date, date))
            if cur.rowcount < 1:
                self.connection.rollback()
                cur.close()
                return 0
            
            trucks_to_maintain = cur.fetchall()

            # find aval. technician
            success = 0

            for truck in trucks_to_maintain:
                not_found_and_exist_match_technician = True
                cur_date = date + dt.timedelta(days = 1)
                while not_found_and_exist_match_technician:
                    # check if there is technician able to maintain trucktype
                    cur.execute("SELECT * FROM technician WHERE trucktype \
                                 = (SELECT trucktype FROM truck WHERE tid = %s);", (truck[0],))
                    if cur.rowcount < 1:
                        not_found_and_exist_match_technician = False # no match technician, do next truck
                    else:
                        # select technician aval. for cur_date & matches trucktype
                        query = ''' (SELECT eid
                                    FROM technician
                                    WHERE trucktype = (SELECT trucktype FROM truck WHERE tid = %s))
                                    EXCEPT 
                                    (SELECT eid FROM maintenance
                                    WHERE %s::date - mdate::date = 0)
                                    ORDER BY eid;
                                '''
                        cur.execute(query, (truck[0], cur_date))
                        if cur.rowcount > 0:
                            not_found_and_exist_match_technician = False # found aval. technician, do next truck
                            success += 1
                            eid = cur.fetchone()
                            cur.execute("INSERT INTO maintenance VALUES (%s, %s, %s);", (truck[0], eid, cur_date))

                    cur_date += dt.timedelta(days = 1)

            self.connection.commit()
            cur.close()

            return success
                    
        except pg.Error as ex:
            # You may find it helpful to uncomment this line while debugging,
            # as it will show you all the details of the error that occurred:
            # raise ex
            return 0

    def reroute_waste(self, fid: int, date: dt.date) -> int:
        """Reroute the trips to <fid> on day <date> to another facility that
        takes the same type of waste. If there are many such facilities, pick
        the one with the smallest fID (that is not <fid>).

        Return the number of re-routed trips.

        Don't worry about too many trips arriving at the same time to the same
        facility. Each facility has ample receiving facility.

        Your method should NOT return an error. If an error occurs, your method
        should simply return 0 i.e., no trips have been re-routed.

        While a realistic use case will provide a <date> in the near future, our
        tests could use any valid value for <date>.

        Assume this happens before any of the trips have reached <fid>.
        """
        try:
            cur = self.connection.cursor()

            # check trip exists on date to fid
            query = ''' SELECT *
                        FROM trip
                        WHERE fid = %s AND
                        ttime::date - %s::date = 0;
                    '''
            cur.execute(query, (fid, date))
            if cur.rowcount < 1: # no trip to fid on date
                self.connection.rollback()
                cur.close()
                return 0
            
            trips_to_reroute = cur.fetchall()
            
            # get best fid
            query = ''' SELECT fid
                        FROM facility
                        WHERE wastetype = (SELECT wastetype
                                            FROM facility
                                            WHERE fid = %s)
                            AND fid <> %s
                        ORDER BY fid;
                        
                    '''
            cur.execute(query, (fid, fid))
            if cur.rowcount < 1: # no other facility aval. for the wastetype
                self.connection.rollback()
                cur.close()
                return 0
            
            alter_f = cur.fetchone()

            cur.execute("UPDATE trip SET fid = %s WHERE fid = %s AND \
                        ttime::date - %s::date = 0;", (alter_f[0], fid, date))
            
            self.connection.commit()
            cur.close()

            return len(trips_to_reroute)
            
        except pg.Error as ex:
            # You may find it helpful to uncomment this line while debugging,
            # as it will show you all the details of the error that occurred:
            # raise ex
            return 0

    # =========================== Helper methods ============================= #

    @staticmethod
    def _read_qualifications_file(file: TextIO) -> list[list[str, str, str]]:
        """Helper for update_technicians. Accept an open file <file> that
        follows the format described on the A2 handout and return a list
        representing the information in the file, where each item in the list
        includes the following 3 elements in this order:
            * The first name of the technician.
            * The last name of the technician.
            * The truck type that the technician is currently qualified to work
              on.

        Pre-condition:
            <file> follows the format given on the A2 handout.
        """
        result = []
        employee_info = []
        for idx, line in enumerate(file):
            if idx % 2 == 0:
                info = line.strip().split(' ')[-2:]
                fname, lname = info
                employee_info.extend([fname, lname])
            else:
                employee_info.append(line.strip())
                result.append(employee_info)
                employee_info = []

        return result


def setup(dbname: str, username: str, password: str, file_path: str) -> None:
    """Set up the testing environment for the database <dbname> using the
    username <username> and password <password> by importing the schema file
    and the file containing the data at <file_path>.
    """
    connection, cursor, schema_file, data_file = None, None, None, None
    try:
        # Change this to connect to your own database
        connection = pg.connect(
            dbname=dbname, user=username, password=password,
            options="-c search_path=waste_wrangler"
        )
        cursor = connection.cursor()

        schema_file = open("./waste_wrangler_schema.sql", "r")
        cursor.execute(schema_file.read())

        data_file = open(file_path, "r")
        cursor.execute(data_file.read())

        connection.commit()
    except Exception as ex:
        connection.rollback()
        raise Exception(f"Couldn't set up environment for tests: \n{ex}")
    finally:
        if cursor and not cursor.closed:
            cursor.close()
        if connection and not connection.closed:
            connection.close()
        if schema_file:
            schema_file.close()
        if data_file:
            data_file.close()

def setup_more_data(self) -> None:
    #helper to add tuples for more testings
    cur = self.connection.cursor()
    
    query = '''INSERT INTO wastetype VALUES ('other');
                INSERT INTO trucktype VALUES ('F', 'landfill'), ('G' , 'electronic waste');
                INSERT INTO truck VALUES (111, 'G', 20);
                DELETE FROM driver WHERE trucktype = 'C' AND eid = 4;

                INSERT INTO employee VALUES 
                (10, 'Yiyu Li', '2000-02-27'),
                (11, 'Jiawei Shi', '2000-02-27'),
                (12, 'Angela Zhao', '2000-02-27'),
                (13, 'Mandy Ma', '2000-02-27'),
                (14, 'Millie Zhu', '2000-02-27');

                INSERT INTO driver VALUES 
                (4, 'B'),
                (10, 'E'),
                (11, 'E'),
                (12, 'E'),
                (13, 'E'),
                (14, 'E');

                INSERT INTO route VALUES
                (2, 'plastic recycling', 10), 
                (3, 'plastic recycling', 5), 
                (4, 'plastic recycling', 10), 
                (5, 'plastic recycling', 20), 
                (11, 'aluminum containers', 5),
                (12, 'aluminum containers', 5),
                (13, 'aluminum containers', 5),
                (15, 'aluminum containers', 5),
                (6, 'compost', 5),
                (7, 'other', 20),
                (8, 'compost', 15);

                
                INSERT INTO trip VALUES 
                (15, 6, '2023-05-04 08:00', NULL, 12, 11, 5),
                (11, 7, '2023-05-04 08:00', NULL, 13, 12, 5),
                (12, 6, '2023-05-05 08:00', NULL, 11, 10, 5),
                (13, 7, '2023-05-05 08:00', NULL, 14, 10, 5);

                INSERT INTO maintenance VALUES (3, 7, '2022-09-25');

            '''
    cur.execute(query)
    cur.close()




def test_preliminary() -> None:
    """Test preliminary aspects of the A2 methods."""
    ww = WasteWrangler()
    qf = None
    try:
        # Change the values of the following variables to connect to your
        # own database:
        dbname = 'postgres'
        user = 'postgres'
        password = 'password'

        connected = ww.connect(dbname, user, password)

        # The following is an assert statement. It checks that the value for
        # connected is True. The message after the comma will be printed if
        # that is not the case (connected is False).
        # Use the same notation to thoroughly test the methods we have provided
        assert connected, f"[Connected] Expected True | Got {connected}."

        # TODO: Test one or more methods here, or better yet, make more testing
        #   functions, with each testing a different aspect of the code.

        # The following function will set up the testing environment by loading
        # the sample data we have provided into your database. You can create
        # more sample data files and use the same function to load them into
        # your database.
        # Note: make sure that the schema and data files are in the same
        # directory (folder) as your a2.py file.
        setup(dbname, user, password, './waste_wrangler_data.sql')
        setup_more_data(ww)

        # --------------------- Testing schedule_trip  ------------------------#

        # You will need to check that data in the Trip relation has been
        # changed accordingly. The following row would now be added:
        # (1, 1, '2023-05-04 08:00', null, 2, 1, 1)
        scheduled_trip = ww.schedule_trip(1, dt.datetime(2023, 5, 4, 8, 0))
        assert scheduled_trip, \
            f"[Schedule Trip] Expected True, Got {scheduled_trip}"

        # Can't schedule the same route of the same day.
        scheduled_trip = ww.schedule_trip(1, dt.datetime(2023, 5, 4, 13, 0))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # invalid route id
        scheduled_trip = ww.schedule_trip(10, dt.datetime(2023, 5, 1, 13, 0))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # no available truck - no match in wastetype
        scheduled_trip = ww.schedule_trip(7, dt.datetime(2023, 5, 1, 13, 0))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # works, now both tid 1 & 2 are out (the only 2 trucks collect 'plastic rec.')
        # tid1 : out on rid 1 from 8:00 to 11:00 with eid 2, 1
        # tid2 : out on rid 2 from 10:00 to 12:00 with eid 3, 4
        scheduled_trip = ww.schedule_trip(2, dt.datetime(2023, 5, 4, 10, 0))
        assert scheduled_trip, \
            f"[Schedule Trip] Expected True, Got {scheduled_trip}"
        
        # no available truck - start time overlap
        scheduled_trip = ww.schedule_trip(3, dt.datetime(2023, 5, 4, 11, 29))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # no available truck - end time overlap
        scheduled_trip = ww.schedule_trip(3, dt.datetime(2023, 5, 4, 8, 31))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # works, tid4 : out on rid 6 collect. 'compost' from 13:00 to 14:00
        # now tid3 is an aval. truck
        scheduled_trip = ww.schedule_trip(6, dt.datetime(2023, 5, 5, 13, 0))
        assert scheduled_trip, \
            f"[Schedule Trip] Expected True, Got {scheduled_trip}"
        
        # no available driver - start time overlap
        scheduled_trip = ww.schedule_trip(8, dt.datetime(2023, 5, 5, 14, 29))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # no available driver - end time overlap
        scheduled_trip = ww.schedule_trip(8, dt.datetime(2023, 5, 5, 12, 31))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # no fid
        scheduled_trip = ww.schedule_trip(7, dt.datetime(2023, 5, 1, 13, 0))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # end time exceeds working hrs
        scheduled_trip = ww.schedule_trip(1, dt.datetime(2023, 6, 1, 14, 0))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # start time exceeds working hrs
        scheduled_trip = ww.schedule_trip(1, dt.datetime(2023, 6, 1, 17, 0))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"
        
        # start time early than working hrs
        scheduled_trip = ww.schedule_trip(1, dt.datetime(2023, 6, 1, 7, 0))
        assert not scheduled_trip, \
            f"[Schedule Trip] Expected False, Got {scheduled_trip}"

        # -------------------- Testing schedule_trips  ------------------------#

        # tid4 : trucktype 'C', collects 'compost' out on 5.3
        # no other driver can drive this trucktype
        scheduled_trips = ww.schedule_trips(4, dt.datetime(2023, 5, 3))
        assert scheduled_trips == 0, \
            f"[Schedule Trips] Expected 0, Got {scheduled_trips}"
        
        # no available driver
        scheduled_trips = ww.schedule_trips(3, dt.datetime(2023, 5, 3))
        assert scheduled_trips == 0, \
            f"[Schedule Trips] Expected 0, Got {scheduled_trips}"
        
        #success case, tid = 1
        scheduled_trips = ww.schedule_trips(6, dt.datetime(2023, 5, 16))
        assert scheduled_trips == 4, \
            f"[Schedule Trips] Expected 4, Got {scheduled_trips}"

        # ----------------- Testing update_technicians  -----------------------#

        # This uses the provided file. We recommend you make up your custom
        # file to thoroughly test your implementation.
        # You will need to check that data in the Technician relation has been
        # changed accordingly

        # existed pairs, driver, incorrect employee name, incorrect trucktype
        qf = open('qualifications.txt', 'r')
        updated_technicians = ww.update_technicians(qf)
        assert updated_technicians == 2, \
            f"[Update Technicians] Expected 2, Got {updated_technicians}"

        # ----------------- Testing workmate_sphere ---------------------------#

        # This employee doesn't exist in our instance
        workmate_sphere = ww.workmate_sphere(2023)
        assert len(workmate_sphere) == 0, \
            f"[Workmate Sphere] Expected [], Got {workmate_sphere}"

        workmate_sphere = ww.workmate_sphere(3)
        # Use set for comparing the results of workmate_sphere since
        # order doesn't matter.
        # Notice that 2 is added to 1's work sphere because of the trip we
        # added earlier.
        assert set(workmate_sphere) == {1, 2, 4}, \
            f"[Workmate Sphere] Expected {{1, 2, 4}}, Got {workmate_sphere}"
        
        # similar test, more employees
        workmate_sphere = ww.workmate_sphere(11)
        assert set(workmate_sphere) == {10, 12, 13, 14}, \
            f"[Workmate Sphere] Expected {{10, 12, 13, 14}}, Got {workmate_sphere}"

        # ----------------- Testing schedule_maintenance ----------------------#

        # You will need to check the data in the Maintenance relation
        scheduled_maintenance = ww.schedule_maintenance(dt.date(2022, 9, 15))
        assert scheduled_maintenance == 4, \
            f"[Schedule Maintenance] Expected 4, Got {scheduled_maintenance}"
        
        # no truck needs maintenance & no technician for trucktype 'G'
        scheduled_maintenance = ww.schedule_maintenance(dt.date(2022, 9, 16))
        assert scheduled_maintenance == 0, \
            f"[Schedule Maintenance] Expected 0, Got {scheduled_maintenance}"

        # ------------------ Testing reroute_waste  ---------------------------#

        # There is no trips to facility 1 on that day
        reroute_waste = ww.reroute_waste(1, dt.date(2023, 5, 10))
        assert reroute_waste == 0, \
            f"[Reroute Waste] Expected 0. Got {reroute_waste}"

        # You will need to check that data in the Trip relation has been
        # changed accordingly
        reroute_waste = ww.reroute_waste(1, dt.date(2023, 5, 3))
        assert reroute_waste == 1, \
            f"[Reroute Waste] Expected 1. Got {reroute_waste}"
    finally:
        if qf and not qf.closed:
            qf.close()
        ww.disconnect()


if __name__ == '__main__':
    # Un comment-out the next two lines if you would like to run the doctest
    # examples (see ">>>" in the methods connect and disconnect)
    # import doctest
    # doctest.testmod()

    # TODO: Put your testing code here, or call testing functions such as
    #   this one:
    test_preliminary()
