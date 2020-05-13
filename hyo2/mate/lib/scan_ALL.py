from collections import namedtuple
from copy import copy
from datetime import *
import functools
import os
import struct
import pyall

from hyo2.mate.lib.scan import Scan, A_NONE, A_PARTIAL, A_FULL, A_FAIL, A_PASS
from hyo2.mate.lib.scan import ScanState, ScanResult


class ScanALL(Scan):
    '''scan an ALL file and provide some indicators of the contents'''

    def __init__(self, file_path):
        Scan.__init__(self, file_path)
        self.reader = open(self.file_path, 'rb')
        self.all_reader = pyall.ALLReader(self.file_path)

    def get_size_n_pings(self, pings):
        '''
        return bytes in the file which containg specified
        number of pings
        '''
        c_bytes = 0
        result = {}
        self.all_reader.rewind()

        while self.all_reader.readDatagramHeader():
            # read datagram header
            header = self.all_reader.readDatagramHeader()
            num_bytes, stx, dg_type, em_model, record_date, record_time, \
                counter, serial_number = header

            dg_type, datagram = self.all_reader.readDatagram()

            c_bytes += num_bytes
            if dg_type in ['D', 'X', 'F', 'f', 'N', 'S', 'Y']:
                if dg_type not in result.keys():
                    result[dg_type] = {
                        'seqNo': counter,
                        'count': 0,
                    }
                if counter > result[dg_type]['seqNo']:
                    result[dg_type]['count'] += 1
                    if result[dg_type]['count'] > pings:
                        break
                result[dg_type]['seqNo'] = counter
            else:
                return None
        return c_bytes

    def __push_datagram(self, datagram_char, datagram):
        '''
        util function to cut boiler plate code on adding to the datagrams dict
        :param datagram_char: The single character identifier for this
            datagram. eg; `I`, `h`
        :param datagram: The datagram object
        '''

        # Use the datagram id character as the key to store values in the
        # cache dict. Most users/developers are familiar with this
        name = datagram_char

        # keep a list of datagrams in the datagram dict. If one hasn't been
        # added with this name yet create a new array
        if name not in self.datagrams:
            self.datagrams[name] = []
        self.datagrams[name].append(datagram)

    def scan_datagram(self, progress_callback=None):
        '''scan data to extract basic information for each type of datagram'''

        # summary type information stored in plain dict
        self.scan_result = {}
        # datagram objects
        self.datagrams = {}
        while self.all_reader.moreData():
            # update progress
            self.progress = 1.0 - (self.all_reader.moreData() / self.file_size)
            if progress_callback is not None:
                progress_callback(self.progress)

            # read datagram header
            header = self.all_reader.readDatagramHeader()
            num_bytes, stx, dg_type, em_model, record_date, record_time, \
                counter, serial_number = header
                
            time_stamp = pyall.to_DateTime(record_date, record_time)

            dg_type, datagram = self.all_reader.readDatagram()
            # print( (dg_type, datagram) )

            if dg_type not in self.scan_result.keys():
                self.scan_result[dg_type] = copy(self.default_info)
                self.scan_result[dg_type]['_seqNo'] = None

            # save datagram info
            self.scan_result[dg_type]['byteCount'] += num_bytes
            self.scan_result[dg_type]['recordCount'] += 1
            if self.scan_result[dg_type]['startTime'] is None:
                self.scan_result[dg_type]['startTime'] = time_stamp
            self.scan_result[dg_type]['stopTime'] = time_stamp

            if dg_type == 'I':
                # Instrument parameters
                # we care about this datagram so read its contents
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'h':
                # height
                if 'h' not in self.datagrams:
                    # only read the first h datagram, this is all we need
                    # to check the height type (assuming all h datagrams)
                    # share the same type
                    datagram.read()
                    self.__push_datagram(dg_type, datagram)
            elif dg_type == 'R':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'A':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'n':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'P':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'G':
                # problem
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'U':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'D':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'X':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'F':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'f':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'N':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'S':
                datagram.read()
                self.__push_datagram(dg_type, datagram)
            elif dg_type == 'Y':
                datagram.read()
                self.__push_datagram(dg_type, datagram)

            if dg_type in ['D', 'X', 'F', 'f', 'N', 'S', 'Y']:
                this_count = counter
                last_count = self.scan_result[dg_type]['_seqNo']
                if last_count is None:
                    last_count = this_count
                if this_count - last_count >= 1:
                    self.scan_result[dg_type]['missedPings'] += \
                        this_count - last_count - 1
                    self.scan_result[dg_type]['pingCount'] += 1
                self.scan_result[dg_type]['_seqNo'] = this_count
        return

    def get_installation_parameters(self):
        '''
        Gets the decoded contents of the I datagram (installation parameters)
        as a Python dict. If multiple I datagrams are included only decoded
        parameters from the first will be included.
        Will return None if datagram not present in *.all file
        '''
        if 'I' not in self.datagrams:
            return None

        installationParametersDatagrams = self.datagrams['I']
        for installationParametersDatagram in installationParametersDatagrams:
            # skip datagrams with no params
            if len(installationParametersDatagram.installationParameters) == 0:
                continue
            return installationParametersDatagram.installationParameters

        return None

    def get_datagram_format_version(self):
        '''
        gets the version of the datagram format used by this file
        '''
        rec = self.get_installation_parameters()
        dsv = None
        if rec is not None and 'DSV' in rec.keys():
            dsv = rec['DSV']
        return dsv

    def is_filename_changed(self):
        '''
        check if the filename is different from what recorded
        in the datagram. Requires `I` datagram
        '''
        if 'I' not in self.datagrams:
            # then there's no way to check, so fail test
            return False

        installationParametersDatagrams = self.datagrams['I']
        for installationParametersDatagram in installationParametersDatagrams:

            if 'RFN' not in installationParametersDatagram.installationParameters:
                # then filename hasn't been included
                continue

            rfn = installationParametersDatagram.installationParameters['RFN']
            matched = os.path.basename(self.file_path) != rfn
            if matched:
                return True

        # then none of the installation parameter datagrams included the
        # filename that this data has been loaded from.
        return False

    def is_date_match(self):
        '''
        compare the date as in the datagram I and the date as written
        in the filename recorded in the datagram I
        return: True/False
        '''
        dt = 'unknown'
        rec = self.get_datagram_info('I')
        if rec is not None:
            dt = rec['startTime'].strftime('%Y%m%d')
        return dt in os.path.basename(self.file_path)

    def bathymetry_availability(self) -> ScanResult:
        '''
        check the presence of all required datagrams for bathymetry processing
        return: ScanResult
        '''

        # define a named tuple for bathy datagrams. Provides a means to define
        # then reference this info.
        Datagram = namedtuple(
            'Datagram',
            'id critical error_message alternatives'
        )

        bathy_datagrams = [
            Datagram(
                'I',
                False,
                "Warning: installation parameters are missing please ensure that you have your lever arms and vessel frame parameters collected elsewhere.",
                []
            ),
            Datagram(
                'R',
                False,
                "Warning: runtime parameters are missing these are critical for backscatter processing streams.  If just collecting bathymetry, please consider other users of this data.",
                []
            ),
            Datagram(
                'A',
                True,
                "Critical: runtime parameters are missing these are critical for backscatter processing streams.  If just collecting bathymetry, please consider other users of this data.",
                []
            ),
            Datagram(
                'n',
                False,
                "Warning: your network attitude and velocity is not being logged.  If you intend working in deeper water with a frequency modulated chirp you will need to interface this data.",
                []
            ),
            Datagram(
                'P',
                True,
                "Critical: position data missing, you will not be able to process this data without ensuring this data is being collected.",
                []
            ),
            Datagram(
                'G',
                False,
                "Warning: surface sound velocity data is missing, ensure your sensor is working or collect as many profiles as possible to attempt to compensate.",
                []
            ),
            Datagram(
                'U',
                False,
                "Warning: no sound velocity profile data has been collected in the raw file, please ensure you are collecting this data elsewhere.",
                []
            ),
            Datagram(
                'D',
                False,
                "Warning: neither datagram 'D' or 'X' were found, processed depth information is missing.",
                ['X']
            ),
            Datagram(
                'F',
                True,
                "Critical: neither datagram 'F', 'f' or 'N' were found. Critical range and angle data missing, you are not collecting the data required for post processing.  If you are collecting processed depths it is possible to back process however it is not desirable and is a complex process.",
                ['f', 'N']
            )
        ]

        return self.__result_from_datagram_presence(bathy_datagrams)

    def backscatter_availability(self) -> ScanResult:
        '''
        check the presence of all required datagrams for backscatter processing
        return: ScanResult
        '''

        # define a named tuple for datagrams. Provides a means to define
        # then reference this info.
        Datagram = namedtuple(
            'Datagram',
            'id critical error_message alternatives'
        )

        bs_datagrams = [
            Datagram(
                'S',
                True,
                "Critical: backscatter information is missing ('S' or 'Y' datagram).  You will not be able to process backscatter without seabed image data.  If you intend processing backscatter check your setup.",
                ['Y']
            )
        ]
        return self.__result_from_datagram_presence(bs_datagrams)

    def ray_tracing_availability(self) -> ScanResult:
        '''
        check the presence of all required datagrams for ray tracing processing
        return: ScanResult
        '''

        # define a named tuple for datagrams. Provides a means to define
        # then reference this info.
        Datagram = namedtuple(
            'Datagram',
            'id critical error_message alternatives'
        )

        rt_datagrams = [
            Datagram(
                'I',
                False,
                "Warning: installation parameters are missing please ensure that you have your lever arms and vessel frame parameters collected elsewhere.",
                []
            ),
            Datagram(
                'R',
                False,
                "Warning: runtime parameters are missing these are critical for backscatter processing streams.  If just collecting bathymetry, please consider other users of this data.",
                []
            ),
            Datagram(
                'A',
                True,
                "Critical: runtime parameters are missing these are critical for backscatter processing streams.  If just collecting bathymetry, please consider other users of this data.",
                []
            ),
            Datagram(
                'n',
                False,
                "Warning: your network attitude and velocity is not being logged.  If you intend working in deeper water with a frequency modulated chirp you will need to interface this data.",
                []
            ),
            Datagram(
                'P',
                True,
                "Critical: position data missing, you will not be able to process this data without ensuring this data is being collected.",
                []
            ),
            Datagram(
                'G',
                False,
                "Warning: surface sound velocity data is missing, ensure your sensor is working or collect as many profiles as possible to attempt to compensate.",
                []
            ),
            Datagram(
                'U',
                False,
                "Warning: no sound velocity profile data has been collected in the raw file, please ensure you are collecting this data elsewhere.",
                []
            ),
            Datagram(
                'F',
                True,
                "Critical: neither datagram 'F', 'f' or 'N' were found. Critical range and angle data missing, you are not collecting the data required for post processing.  If you are collecting processed depths it is possible to back process however it is not desirable and is a complex process.",
                ['f', 'N']
            )
        ]

        return self.__result_from_datagram_presence(rt_datagrams)

    def __result_from_datagram_presence(self, required_datagrams):
        '''
        Util function, checks the datagrams that have been read during the
        scan against the `required_datagrams` list. Critical vs Warning, and
        associated messages are extracted from the attributes of the datagram
        tuples in `required_datagrams`
        return: a ScanResult
        '''
        # tl;dr this cuts down on amount of code that was duplicated across
        # a number of check functions

        present_datagrams = self.datagrams.keys()

        all_critical = True
        all_noncritical = True
        missing_critical = []
        missing_noncritical = []
        messages = []

        for required_datagram in required_datagrams:
            # the bathy datagram was not read from file
            not_found = required_datagram.id not in present_datagrams
            if not_found:
                # it may be that one of the alternative datagrams exist, so
                # loop through these to see if they exist
                found_in_alts = functools.reduce(
                    lambda a,b : (b in present_datagrams) or a, required_datagram.alternatives,
                    False)
                not_found = not found_in_alts

            if not_found and required_datagram.critical:
                all_critical = False
                missing_critical.append(required_datagram.id)
                messages.append(required_datagram.error_message)
            elif not_found and not required_datagram.critical:
                all_noncritical = False
                missing_noncritical.append(required_datagram.id)
                messages.append(required_datagram.error_message)

        # include a lists of missing datagrams in result object
        data = {
            'missing_critical': missing_critical,
            'missing_noncritical': missing_noncritical
        }

        if not all_critical:
            return ScanResult(
                state=ScanState.FAIL,
                messages=messages,
                data=data
            )
        elif not all_noncritical:
            return ScanResult(
                state=ScanState.WARNING,
                messages=messages,
                data=data
            )
        else:
            return ScanResult(
                state=ScanState.PASS,
                messages=messages
            )

    def is_missing_pings_tolerable(self, thresh=1.0):
        '''
        check for the number of missing pings in all multibeam
        data datagrams (D or X, F or f or N, S or Y)
        (allow the difference <= 1%)
        return: True/False
        '''
        for d_type in ['D', 'X', 'F', 'f', 'N', 'S', 'Y']:
            if d_type in self.scan_result.keys():
                rec = self.scan_result[d_type]
                if rec['pingCount'] == 0:
                    continue
                if rec['missedPings'] * 100.0 / rec['pingCount'] > thresh:
                    return False
        return True

    def has_minimum_pings(self, thresh=10):
        '''
        check if we have minimum number of requied pings in all multibeam
        data datagrams (D or X, F or f or N, S or Y)
        (minimum number is 10)
        return: True/False
        '''
        for d_type in ['D', 'X', 'F', 'f', 'N', 'S', 'Y']:
            if d_type in self.scan_result.keys():
                rec = self.scan_result[d_type]
                if rec['pingCount'] < thresh:
                    return False
        return True

    def ellipsoid_height_availability(self):
        '''
        check the presence of the datagrams h and the height type is 0 (The
        height is derived from the GGK or GGA datagram and is the height of
        the water level at the vertical datum (possibly motion corrected).)
        All parsed 'h' datagrams must have the height type of 0 to pass. BUT
        currently only the first 'h' datagram is read (for performance reasons)
        return: True/False
        '''

        if 'h' not in self.datagrams:
            # then there's no way to check, so fail test
            return False

        heightDatagrams = self.datagrams['h']
        firstHeightDatagram = heightDatagrams[0]
        return firstHeightDatagram.HeightType == 0

    def ellipsoid_height_setup(self)  -> ScanResult:
        '''
        check the input positioning system string will likely contain heights
        that are referenced to the ellipsoid and provide feedback that suggests
        how to rectify if not
        Logic is that if a PosMV or F180 is interfaced the interfaced string
        needs to be a GGK message
        if a seapath binary message is interfaced then there is no way to determine
        which system is interfaced and the user will need to check documentation
        to ensure the string interfaced for positioning contains ellipsoid heights

        return: ScanResult
        '''

        if 'n' not in self.datagrams:
            return ScanResult(
                state=ScanState.WARNING,
                messages="Unable to conduct height setup check.  No network attitude and velocity datagrams",
                data={})
        
        inputtelegramsize = self.datagrams['n'][0].Attitude[0][6]
        rawposinput = self.datagrams['P'][0].data[2:5]
        if inputtelegramsize == 137:
            inertialSystem = 'PosMV'
        elif inputtelegramsize == 45 or inputtelegramsize == 43:
            inertialSystem = 'Other'
        else:
            intertialSystem = 'F180'

        data = {
            'inertial_pos_system': inertialSystem,
            'pos_string': rawposinput
        }

        if inertialSystem == 'PosMV' or inertialSystem == 'F180' and rawposinput == 'GGK':
            return ScanResult(
                state=ScanState.PASS,
                messages='',
                data=data
            )
        elif inertialSystem == 'Other':
            return ScanResult(
                state=ScanState.WARNING,
                messages="Unable to determine positioning system.  Check position input contains ellipsoid heights",
                data=data
            )
        else:
            return ScanResult(
                state=ScanState.FAIL,
                messages="Ellipsoid heights not being logged change your position input to a GGK string",
                data=data
            )
