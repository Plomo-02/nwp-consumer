"""nwp-consumer.

Usage:
  nwp-consumer download --source=SOURCE [--sink=SINK --from=FROM --to=TO --rdir=RDIR --zdir=ZDIR --create-latest]
  nwp-consumer convert --source=SOURCE [--sink=SINK --from=FROM --to=TO --rdir=RDIR --zdir=ZDIR --rsink=RSINK --create-latest]
  nwp-consumer consume --source=SOURCE [--sink=SINK --from=FROM --to=TO --rdir=RDIR --zdir=ZDIR --rsink=RSINK --create-latest]
  nwp-consumer env (--source=SOURCE | --sink=SINK)
  nwp-consumer check [--sink=SINK] [--rdir=RDIR] [--zdir=ZDIR]
  nwp-consumer (-h | --help)
  nwp-consumer --version

Commands:
  download            Download raw data from source to sink
  convert             Convert raw data present in sink
  consume             Download and convert raw data from source to sink
  check               Perform a healthcheck on the service
  env                 Print the unset environment variables required by the source/sink

Options:
  --from=FROM         Start datetime in YYYY-MM-DDTHH:MM or YYYY-MM-DD format [default: today].
  --to=TO             End datetime in YYYY-MM-DD or YYYY-MM-DDTHH:MM format.
  --source=SOURCE     Data source (ceda/metoffice/ecmwf-mars/ecmwf-s3/icon/cmc).
  --sink=SINK         Data sink (local/s3/huggingface) [default: local].
  --rsink=RSINK       Data sink for raw data, if different (local/s3/huggingface) [default: SINK].
  --rdir=RDIR         Directory of raw data store [default: /tmp/raw].
  --zdir=ZDIR         Directory of zarr data store [default: /tmp/zarr].
  --create-latest     Create a zarr of the dataset with the latest init time [default: False].

Generic Options:
  --version           Show version.
  -h, --help          Show this screen.
  -v, --verbose       Enable verbose logging [default: False].
"""

import contextlib
import datetime as dt
import importlib.metadata
import pathlib
import shutil
import sys

import dask
import dask.distributed
import structlog
from docopt import docopt

from nwp_consumer import internal
from nwp_consumer.internal import config, inputs, outputs
from nwp_consumer.internal.service import NWPConsumerService

__version__ = "local"

with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version("package-name")

log = structlog.getLogger()


def run(argv: list[str]) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """Run the CLI.

    Args:
        argv: The command line arguments.

    Returns:
        A tuple of lists of raw and processed files.
    """
    # --- Map environment variables to service configuration --- ## Configure dask

    dask.config.set({"array.slicing.split_large_chunks": True})
    if config.ConsumerEnv().DASK_SCHEDULER_ADDRESS != "":
        # Connect to the dask scheduler if the address is set
        # * This becomes the default client for all dask operations
        client = dask.distributed.Client(
            address=config.ConsumerEnv().DASK_SCHEDULER_ADDRESS,
        )
        log.info(
            event="Connected to dask scheduler",
            address=config.ConsumerEnv().DASK_SCHEDULER_ADDRESS,
        )

    # --- Map arguments to service configuration --- #

    arguments = docopt(__doc__, argv=argv, version=__version__)
    storer = _parse_sink(arguments["--sink"])
    fetcher = _parse_source(arguments["--source"])
    # Set the raw sink to the same as the zarr sink if not specified
    rawstorer = storer if arguments["--rsink"] == "SINK" else _parse_sink(arguments["--rsink"])
    start, end = _parse_from_to(arguments["--from"], arguments["--to"])

    # Create the service using the fetcher and storer
    service = NWPConsumerService(
        fetcher=fetcher,
        storer=storer,
        rawstorer=rawstorer,
        zarrdir=arguments["--zdir"],
        rawdir=arguments["--rdir"],
    )

    # --- Run the service with the desired command --- #

    # Logic for the "check" command
    if arguments["check"]:
        _ = service.Check()
        return ([], [])

    # Logic for the env command
    if arguments["env"]:
        # Missing env vars are printed during mapping of source/sink args
        return ([], [])

    # Logic for the other commands
    log.info("nwp-consumer service starting", version=__version__, arguments=arguments)
    rawFiles: list[pathlib.Path] = []
    processedFiles: list[pathlib.Path] = []

    if arguments["download"]:
        rawFiles += service.DownloadRawDataset(start=start, end=end)

    if arguments["convert"]:
        processedFiles += service.ConvertRawDatasetToZarr(start=start, end=end)

    if arguments["consume"]:
        service.Check()
        r, p = service.DownloadAndConvert(start=start, end=end)
        rawFiles += r
        processedFiles += p

    if arguments["--create-latest"]:
        processedFiles += service.CreateLatestZarr()

    return rawFiles, processedFiles


def main() -> None:
    """Entry point for the nwp-consumer CLI."""
    erred = False

    programStartTime = dt.datetime.now(tz=dt.UTC)
    try:
        files: tuple[list[pathlib.Path], list[pathlib.Path]] = run(argv=sys.argv[1:])
        log.info(
            event="processed files",
            raw_files=len(files[0]),
            processed_files=len(files[1]),
        )
    except Exception as e:
        log.error("encountered error running nwp-consumer", error=str(e), exc_info=True)
        erred = True
    finally:
        clearableCache: list[pathlib.Path] = list(internal.CACHE_DIR.glob("*"))
        for p in clearableCache:
            if p.exists() and p.is_dir():
                shutil.rmtree(p)
            if p.is_file():
                p.unlink(missing_ok=True)
        elapsedTime = dt.datetime.now(tz=dt.UTC) - programStartTime
        log.info(event="nwp-consumer finished", elapsed_time=str(elapsedTime), version=__version__)
        if erred:
            exit(1)


if __name__ == "__main__":
    main()


def _parse_from_to(fr: str, to: str | None) -> tuple[dt.datetime, dt.datetime]:
    """Process the from and to arguments."""
    # Modify the default "today" argument to today's date
    if fr == "today":
        fr = dt.datetime.now(tz=dt.UTC).strftime("%Y-%m-%d")
    # If --from specifies a date, and --to is not set, set --to to the next day
    if len(fr) == 10 and to is None:
        to = (
            dt.datetime.strptime(
                fr,
                "%Y-%m-%d",
            ).replace(tzinfo=dt.UTC)
            + dt.timedelta(days=1)
        ).strftime("%Y-%m-%d")
    # Otherwise, --from specifies a datetime,
    # so if --to is not set, set --to to the same time
    if to is None:
        to = fr
    # If --from and --to are missing time information, assume midnight
    if len(fr) == 10:
        fr += "T00:00"
    if len(to) == 10:
        to += "T00:00"
    # Process to datetime objects
    start: dt.datetime = dt.datetime.strptime(
        fr,
        "%Y-%m-%dT%H:%M",
    ).replace(tzinfo=dt.UTC)
    end: dt.datetime = dt.datetime.strptime(
        to,
        "%Y-%m-%dT%H:%M",
    ).replace(tzinfo=dt.UTC)

    if end < start:
        raise ValueError("argument '--from' cannot specify date prior to '--to'")

    return start, end


def _parse_source(source: str) -> internal.FetcherInterface:
    """Parse the source argument into a fetcher interface."""
    # Set defaults for fetcher and env for typesafe assignments
    fetcher: internal.FetcherInterface = inputs.ceda.Client(
        ftpUsername="not-set",
        ftpPassword="not-set",
    )
    env: config.EnvParser = config.LocalEnv()

    match source:
        case "ceda":
            env: config.CEDAEnv = config.CEDAEnv()
            fetcher = inputs.ceda.Client(
                ftpUsername=env.CEDA_FTP_USER,
                ftpPassword=env.CEDA_FTP_PASS,
            )
        case "metoffice":
            env: config.MetOfficeEnv = config.MetOfficeEnv()
            fetcher = inputs.metoffice.Client(
                orderID=env.METOFFICE_ORDER_ID,
                apiKey=env.METOFFICE_API_KEY,
            )
        case "ecmwf-mars":
            env: config.ECMWFMARSEnv = config.ECMWFMARSEnv()
            fetcher = inputs.ecmwf.MARSClient(
                area=env.ECMWF_AREA,
                hours=env.ECMWF_HOURS,
                param_group=env.ECMWF_PARAMETER_GROUP,
            )
        case "ecmwf-s3":
            env: config.ECMWFS3Env = config.ECMWFS3Env()
            fetcher = inputs.ecmwf.S3Client(
                area=env.ECMWF_AREA,
                bucket=env.AWS_S3_BUCKET,
                region=env.AWS_REGION,
                key=env.AWS_ACCESS_KEY,
                secret=env.AWS_ACCESS_SECRET,
            )
        case "icon":
            env: config.ICONEnv = config.ICONEnv()
            fetcher = inputs.icon.Client(
                model=env.ICON_MODEL,
                param_group=env.ICON_PARAMETER_GROUP,
                hours=env.ICON_HOURS,
            )
        case "cmc":
            env: config.CMCEnv = config.CMCEnv()
            fetcher = inputs.cmc.Client(
                param_group=env.CMC_PARAMETER_GROUP,
                hours=env.CMC_HOURS,
                model=env.CMC_MODEL,
            )
        case None:
            pass
        case _:
            raise ValueError(
                f"unknown source {source}. Exoected one of (ceda/metoffice/ecmwf-mars/icon/cmc)",
            )
    return fetcher


def _parse_sink(sink: str) -> internal.StorageInterface:
    """Parse the sink argument into a storer interface."""
    storer: internal.StorageInterface = outputs.localfs.Client()
    env: config.EnvParser = config.LocalEnv()

    match sink:
        case "local":
            storer = outputs.localfs.Client()
        case "s3":
            env = config.S3Env()
            storer = outputs.s3.Client(
                bucket=env.AWS_S3_BUCKET,
                key=env.AWS_ACCESS_KEY,
                secret=env.AWS_ACCESS_SECRET,
                region=env.AWS_REGION,
            )
        case "huggingface":
            env = config.HuggingFaceEnv()
            storer = outputs.huggingface.Client(
                token=env.HUGGINGFACE_TOKEN,
                repoID=env.HUGGINGFACE_REPO_ID,
            )
        case None:
            pass
        case _:
            raise ValueError(
                f"unknown sink {sink}. Expected one of (local/s3/huggingface)",
            )
    return storer
