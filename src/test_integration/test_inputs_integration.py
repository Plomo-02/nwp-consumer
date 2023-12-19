"""Integration tests for the `inputs` module.

WARNING: Requires environment variables to be set for the MetOffice and CEDA APIs.
Will download up to a GB of data. Costs may apply for usage of the APIs.
"""

import datetime as dt
import unittest

from nwp_consumer.internal import config, inputs, outputs
from nwp_consumer.internal.inputs.ceda._models import CEDAFileInfo
from nwp_consumer.internal.inputs.ecmwf._models import ECMWFMarsFileInfo
from nwp_consumer.internal.inputs.icon._models import IconFileInfo
from nwp_consumer.internal.inputs.metoffice._models import MetOfficeFileInfo
from nwp_consumer.internal.inputs.cmc._models import CMCFileInfo
from nwp_consumer.internal.inputs.noaa._models import NOAAFileInfo

storageClient = outputs.localfs.Client()


class TestClient_FetchRawFileBytes(unittest.TestCase):
    def test_downloadsRawGribFileFromCEDA(self) -> None:
        c = config.CEDAEnv()
        cedaClient = inputs.ceda.Client(
            ftpUsername=c.CEDA_FTP_USER,
            ftpPassword=c.CEDA_FTP_PASS,
        )

        fileInfo = CEDAFileInfo(name="202201010000_u1096_ng_umqv_Wholesale1.grib")
        _, tmpPath = cedaClient.downloadToTemp(fi=fileInfo)

        self.assertGreater(tmpPath.stat().st_size, 100000000)

    def test_downloadsRawGribFileFromMetOffice(self) -> None:
        metOfficeInitTime: dt.datetime = dt.datetime.now(dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

        c = config.MetOfficeEnv()
        metOfficeClient = inputs.metoffice.Client(
            orderID=c.METOFFICE_ORDER_ID,
            clientID=c.METOFFICE_CLIENT_ID,
            clientSecret=c.METOFFICE_CLIENT_SECRET,
        )
        fileInfo = MetOfficeFileInfo(
            fileId=f'agl_temperature_1.5_{dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d")}00',
            runDateTime=metOfficeInitTime,
        )
        _, tmpPath = metOfficeClient.downloadToTemp(fi=fileInfo)
        self.assertGreater(tmpPath.stat().st_size, 2000000)

    def test_downloadsRawGribFileFromECMWFMARS(self) -> None:
        ecmwfMarsInitTime: dt.datetime = dt.datetime(
            year=2022, month=1, day=1, hour=0, minute=0, tzinfo=dt.UTC,
        )

        ecmwfMarsClient = inputs.ecmwf.mars.Client(
            area="uk",
            hours=4,
        )
        fileInfo = ECMWFMarsFileInfo(
            inittime=ecmwfMarsInitTime,
            area="uk",
        )
        _, tmpPath = ecmwfMarsClient.downloadToTemp(fi=fileInfo)
        self.assertGreater(tmpPath.stat().st_size, 2000000)

    def test_downloadsRawGribFileFromICON(self) -> None:
        iconInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

        iconClient = inputs.icon.Client(
            model="global",
        )
        fileInfo = IconFileInfo(
            it=iconInitTime,
            filename=f"icon_global_icosahedral_single-level_{iconInitTime.strftime('%Y%m%d%H')}_001_CLCL.grib2.bz2",
            currentURL="https://opendata.dwd.de/weather/nwp/icon/grib/00/clcl",
            step=1,
        )
        _, tmpPath = iconClient.downloadToTemp(fi=fileInfo)
        self.assertFalse(tmpPath.name.endswith(".bz2"))
        self.assertLess(len(list(tmpPath.parent.glob("*.bz2"))), 1)
        self.assertGreater(tmpPath.stat().st_size, 40000)

        iconClient = inputs.icon.Client(model="europe")
        fileInfo = IconFileInfo(
            it=iconInitTime,
            filename=f"icon-eu_europe_regular-lat-lon_single-level_{iconInitTime.strftime('%Y%m%d%H')}_001_CLCL.grib2.bz2",
            currentURL="https://opendata.dwd.de/weather/nwp/icon-eu/grib/00/clcl",
            step=1,
        )
        _, tmpPath = iconClient.downloadToTemp(fi=fileInfo)
        self.assertGreater(tmpPath.stat().st_size, 40000)

    def test_downloadsRawGribFileFromCMC(self) -> None:
        cmcInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

        cmcClient = inputs.cmc.Client(
            model="gdps",
        )
        fileInfo = CMCFileInfo(
            it=cmcInitTime,
            filename=f"CMC_glb_VGRD_ISBL_200_latlon.15x.15_{cmcInitTime.strftime('%Y%m%d%H')}_P120.grib2",
            currentURL="https://dd.weather.gc.ca/model_gem_global/15km/grib2/lat_lon/00/120",
            step=1,
        )
        _, tmpPath = cmcClient.downloadToTemp(fi=fileInfo)
        self.assertTrue(tmpPath.name.endswith(".grib2"))
        self.assertGreater(tmpPath.stat().st_size, 40000)

    def test_downloadsRawGribFileFromAWSNOAA(self) -> None:
        noaaInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

        noaaClient = inputs.noaa.aws.Client(
            model="global",
            param_group="basic",
        )
        fileInfo = NOAAFileInfo(
            it=noaaInitTime,
            filename=f"gfs.t00z.pgrb2.0p25.f001",
            currentURL=f"https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{noaaInitTime.strftime('%Y%m%d')}/{noaaInitTime.strftime('%H')}",
            step=1,
        )
        _, tmpPath = noaaClient.downloadToTemp(fi=fileInfo)
        self.assertGreater(tmpPath.stat().st_size, 40000)

    def test_downloadsRawGribFileFromNCARNOAA(self) -> None:
        noaaInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

        noaaClient = inputs.noaa.ncar.Client(
            model="global",
            param_group="basic",
        )
        fileInfo = NOAAFileInfo(
            it=noaaInitTime,
            filename=f"gfs.0p25.2016010300.f003.grib2",
            currentURL=f"https://data.rda.ucar.edu/ds084.1/2016/20160103",
            step=3,
        )
        _, tmpPath = noaaClient.downloadToTemp(fi=fileInfo)
        self.assertGreater(tmpPath.stat().st_size, 40000)

class TestListRawFilesForInitTime(unittest.TestCase):
    def test_getsFileInfosFromCEDA(self) -> None:
        cedaInitTime: dt.datetime = dt.datetime(
            year=2022, month=1, day=1, hour=0, minute=0, tzinfo=dt.UTC,
        )
        c = config.CEDAEnv()
        cedaClient = inputs.ceda.Client(
            ftpUsername=c.CEDA_FTP_USER,
            ftpPassword=c.CEDA_FTP_PASS,
        )
        fileInfos = cedaClient.listRawFilesForInitTime(it=cedaInitTime)
        self.assertTrue(len(fileInfos) > 0)

    def test_getsFileInfosFromMetOffice(self) -> None:
        metOfficeInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        c = config.MetOfficeEnv()
        metOfficeClient = inputs.metoffice.Client(
            orderID=c.METOFFICE_ORDER_ID,
            clientID=c.METOFFICE_CLIENT_ID,
            clientSecret=c.METOFFICE_CLIENT_SECRET,
        )
        fileInfos = metOfficeClient.listRawFilesForInitTime(it=metOfficeInitTime)
        self.assertTrue(len(fileInfos) > 0)

    def test_getsFileInfosFromECMWFMARS(self) -> None:
        ecmwfMarsInitTime: dt.datetime = dt.datetime(
            year=2022, month=1, day=1, hour=0, minute=0, tzinfo=dt.UTC,
        )
        c = config.ECMWFMARSEnv()
        ecmwfMarsClient = inputs.ecmwf.mars.Client(
            area=c.ECMWF_AREA,
            hours=4,
        )
        fileInfos = ecmwfMarsClient.listRawFilesForInitTime(it=ecmwfMarsInitTime)
        self.assertTrue(len(fileInfos) > 0)

    def test_getsFileInfosFromICON(self) -> None:
        iconInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        iconClient = inputs.icon.Client(
            model="global",
            hours=4,
            param_group="basic",
        )
        fileInfos = iconClient.listRawFilesForInitTime(it=iconInitTime)
        self.assertTrue(len(fileInfos) > 0)

        iconClient = inputs.icon.Client(
            model="europe",
            hours=4,
            param_group="basic",
        )
        euFileInfos = iconClient.listRawFilesForInitTime(it=iconInitTime)
        self.assertTrue(len(euFileInfos) > 0)
        self.assertNotEqual(fileInfos, euFileInfos)

    def test_getsFileInfosFromCMC(self) -> None:
        cmcInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        cmcClient = inputs.cmc.Client(
            model="gdps",
            hours=4,
            param_group="basic",
        )
        fileInfos = cmcClient.listRawFilesForInitTime(it=cmcInitTime)
        self.assertTrue(len(fileInfos) > 0)

        cmcClient = inputs.cmc.Client(
            model="geps",
            hours=4,
            param_group="basic",
        )
        gepsFileInfos = cmcClient.listRawFilesForInitTime(it=cmcInitTime)
        self.assertTrue(len(gepsFileInfos) > 0)
        self.assertNotEqual(fileInfos, gepsFileInfos)


    def test_getsFileInfosFromAWSNOAA(self) -> None:
        noaaInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        noaaClient = inputs.noaa.aws.Client(
            model="global",
            hours=4,
            param_group="basic",
        )
        fileInfos = noaaClient.listRawFilesForInitTime(it=noaaInitTime)
        self.assertTrue(len(fileInfos) > 0)

    def test_getsFileInfosFromNCARNOAA(self) -> None:
        noaaInitTime: dt.datetime = dt.datetime.now(tz=dt.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        noaaInitTime = noaaInitTime.replace(year=2017)
        noaaClient = inputs.noaa.ncar.Client(
            model="global",
            hours=4,
            param_group="basic",
        )
        fileInfos = noaaClient.listRawFilesForInitTime(it=noaaInitTime)
        self.assertTrue(len(fileInfos) > 0)


if __name__ == "__main__":
    unittest.main()
