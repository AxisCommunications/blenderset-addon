import logging
import os
import colorama

HOST_FORMAT = "%(asctime)s %(levelname)s %(process)d %(name)s %(message)s"


class HighlightFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        if record.levelno >= logging.ERROR:
            color = colorama.Fore.RED + colorama.Style.BRIGHT
        elif record.levelno >= logging.WARNING:
            color = colorama.Fore.YELLOW + colorama.Style.BRIGHT
        elif record.levelno >= logging.INFO:
            color = colorama.Style.BRIGHT
        else:
            color = colorama.Style.DIM

        return "".join(
            [
                color,
                super().format(record),
                colorama.Style.RESET_ALL,
            ]
        )


def configure_logging(**kwargs):
    """Do custom configuration for the logging system.

    Same as logging.basicConfig except it does the following by default:
    * adds colorization,
    * uses our preferred logging format, and
    * looks for log level in environment variables.
    """
    kwargs.setdefault("format", HOST_FORMAT)
    kwargs.setdefault("level", getattr(logging, os.environ.get("LEVEL", "INFO")))
    handler = logging.StreamHandler()
    handler.setFormatter(HighlightFormatter(kwargs["format"]))
    kwargs.setdefault("handlers", [handler])
    logging.basicConfig(**kwargs)
