"""Contains both ports and domain models for the nwp_consumer package."""

import abc
import datetime as dt
import pathlib
from enum import Enum

import xarray as xr

# ------- Global constants ------- #

# The folder pattern format string for the raw data's init time
IT_FOLDER_FMTSTR = "%Y/%m/%d/%H%M"

# ------- Domain models ------- #

class OCFShortName(str, Enum):
    """Short names for the OCF parameters."""

    LowCloudCover = "lcc"
    MediumCloudCover = "mcc"
    HighCloudCover = "hcc"
    VisibilityAGL = "vis"
    RelativeHumidityAGL = "r"
    RainPrecipitationRate = "prate"
    SnowDepthWaterEquivalent = "sde"
    DownwardShortWaveRadiationFlux = "dswrf"
    DownwardLongWaveRadiationFlux = "dlwrf"
    TemperatureAGL = "t"
    WindSpeedSurfaceAdjustedAGL = "si10"
    WindDirectionFromWhichBlowingSurfaceAdjustedAGL = "wdir10"


class FileInfoModel(abc.ABC):
    """Information about a remote file."""

    @abc.abstractmethod
    def fname(self) -> str:
        """Return the file name."""
        pass

    @abc.abstractmethod
    def initTime(self) -> dt.datetime:
        """Return the init time of the file."""
        pass


# ------- Interfaces ------- #
# Represent ports in the hexagonal architecture pattern

class FetcherInterface(abc.ABC):
    """Generic interface for fetching and converting NWP data from an API.

     Used for dependency injection. NWP data from any source shares common properties:
        - It is presented in one or many files for a given init_time
        - These files can be read as raw bytes
        - There is an expected number of files per init_time which correspond to an equivalent
            number of variables and steps in the dataset

    The following functions define generic transforms based around these principals.
    """

    @abc.abstractmethod
    def listRawFilesForInitTime(self, *, it: dt.datetime) -> list[FileInfoModel]:
        """List the relative path of all files available from source for the given init_time.

        :param it: Init Time to list files for
        """
        pass

    @abc.abstractmethod
    def downloadToTemp(self, *, fi: FileInfoModel) -> tuple[FileInfoModel, pathlib.Path]:
        """Fetch the bytes of a single raw file from source and save to a temp file.

        :param fi: File Info object describing the file to fetch
        :return: Tuple of the File Info object and a path to the local temp file
        """
        pass

    @abc.abstractmethod
    def mapTemp(self, *, p: pathlib.Path) -> xr.Dataset:
        """Create an xarray dataset from the given RAW data in a temp file.

        :param p: Path to temp file holding raw data
        :return: Dataset created from the raw data
        """
        pass


class StorageInterface(abc.ABC):
    """Generic interface for storing data, used for dependency injection."""

    @abc.abstractmethod
    def exists(self, *, dst: pathlib.Path) -> bool:
        """Check if the given path exists.

        :param dst: Path to check
        :return: True if the path exists, False otherwise
        """
        pass

    @abc.abstractmethod
    def store(self, *, src: pathlib.Path, dst: pathlib.Path) -> int:
        """Move the given temp file to the store at path p, deleting the temp file.

        :param src: Path to temp file to move
        :param dst: Desired path in store
        :return: Number of bytes copied
        """
        pass

    @abc.abstractmethod
    def listInitTimes(self, *, prefix: pathlib.Path) -> list[dt.datetime]:
        """List all initTime folders in the given prefix.

        :param prefix: Path to prefix to list initTimes for
        :return: List of initTimes
        """
        pass

    @abc.abstractmethod
    def copyITFolderToTemp(self, *, prefix: pathlib.Path, it: dt.datetime) \
            -> tuple[dt.datetime, list[pathlib.Path]]:
        """Copy all files in given folder to temp files.

        :param prefix: Path of folder in which to find initTimes
        :param it: InitTime to copy files for
        :return: Tuple of the initTime and list of paths to temp files
        """
        pass

    @abc.abstractmethod
    def delete(self, *, p: pathlib.Path) -> None:
        """Delete the given path.

        :param p: Path to delete
        """
        pass
