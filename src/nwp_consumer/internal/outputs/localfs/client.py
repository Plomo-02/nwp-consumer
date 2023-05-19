import pathlib

import numpy as np
import xarray as xr
from ocf_blosc2 import Blosc2
import datetime as dt

from nwp_consumer import internal


class LocalFSClient(internal.StorageInterface):
    """Client for local filesystem."""

    # Location to save raw (Usually GRIB) files
    __rawDir: pathlib.Path

    # Location to save Zarr files
    __zarrDir: pathlib.Path

    def __init__(self, rawDir: str, zarrDir: str, createDirs: bool = False):
        """Create a new LocalFSClient."""
        rawPath: pathlib.Path = pathlib.Path(rawDir)
        zarrPath: pathlib.Path = pathlib.Path(zarrDir)

        if createDirs:
            # If the directories do not exist, create them
            rawPath.mkdir(parents=True, exist_ok=True)
            zarrPath.mkdir(parents=True, exist_ok=True)

        self.__rawDir = rawPath
        self.__zarrDir = zarrPath

    def listFilesInRawDir(self) -> list[pathlib.Path]:
        """List all files in the raw directory."""
        return list(self.__rawDir.glob("**/*"))

    def existsInRawDir(self, fileName: str, initTime: dt.datetime) -> bool:
        """Check if a file exists in the raw directory."""
        path = pathlib.Path(f"{self.__rawDir}/{initTime.strftime('%Y/%m/%d')}/{fileName}")
        return path.exists()

    def existsInZarrDir(self, relativePath: pathlib.Path) -> bool:
        """Check if a file exists in the zarr directory."""
        path = self.__zarrDir / relativePath
        return path.exists()

    def readBytesFromRawDir(self, fileName: str, initTime: dt.datetime) -> bytes:
        """Read a file from the raw dir as bytes."""
        path = pathlib.Path(f"{self.__rawDir}/{initTime.strftime('%Y/%m/%d')}/{fileName}")

        if self.existsInRawDir(fileName=fileName, initTime=initTime):
            return path.read_bytes()
        else:
            raise FileNotFoundError(f"File not found in raw dir: {path}")

    def writeBytesToRawDir(self, fileName: str, initTime: dt.datetime, data: bytes) -> pathlib.Path:
        """Write the given bytes to the raw directory."""
        path = pathlib.Path(f"{self.__rawDir}/{initTime.strftime('%Y/%m/%d')}/{fileName}")

        # Create the path to the file if the folders do not exist
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_bytes(data)
        return path

    def removeFromRawDir(self, fileName: str, initTime: dt.datetime) -> None:
        """Remove a file from the raw dir."""
        path = pathlib.Path(f"{self.__rawDir}/{initTime.strftime('%Y/%m/%d')}/{fileName}")
        path.unlink()

    def saveDataset(self, dataset: xr.Dataset, relativePath: pathlib.Path) -> None:
        """Store the given dataset as zarr."""
        path = self.__zarrDir / relativePath

        chunkedDataset = _createChunkedDaskDataset(dataset)
        del dataset

        # Ensure the zarr path doesn't already exist
        if self.existsInZarrDir(relativePath=relativePath):
            raise ValueError(f"Zarr path already exists: {path}")

        # Create new Zarr store.
        to_zarr_kwargs = dict(
            encoding={
                "init_time": {"units": "nanoseconds since 1970-01-01"},
                "UKV": {
                    "compressor": Blosc2(cname="zstd", clevel=5),
                },
            },
        )

        chunkedDataset["UKV"] = chunkedDataset.astype(np.float16)["UKV"]
        chunkedDataset.to_zarr(path, **to_zarr_kwargs)
        del chunkedDataset

    def appendDataset(self, dataset: xr.Dataset, relativePath: pathlib.Path) -> None:
        """Append the given dataset to the existing Zarr store."""
        path = self.__zarrDir / relativePath

        # Ensure the zarr path already exists
        if not self.existsInZarrDir(relativePath=relativePath):
            raise ValueError(f"Error appending dataset to path {path}: path does not exist")

        # Append to existing Zarr store.
        to_zarr_kwargs = dict(
            append_dim="init_time",
        )

        chunkedDataset = _createChunkedDaskDataset(dataset)
        del dataset

        chunkedDataset["UKV"] = chunkedDataset.astype(np.float16)["UKV"]
        chunkedDataset.to_zarr(path, **to_zarr_kwargs)

        del chunkedDataset


def _createChunkedDaskDataset(ds: xr.Dataset) -> xr.Dataset:
    """Create a chunked Dask Dataset from the input multi-variate Dataset.

    Converts the input multivariate DataSet (with different DataArrays for
    each NWP variable) to a single DataArray with a `variable` dimension.
    This allows each Zarr chunk to hold multiple variables (useful for loading
    many/all variables at once from disk).
    """
    # Create single-variate dataarray from dataset, with new "variable" dimension
    da = ds.to_array(dim="variable", name="UKV")
    del ds

    return (
        da.to_dataset().chunk(
            {
                "init_time": 1,
                "step": 1,
                "variable": -1,
            })
    )
