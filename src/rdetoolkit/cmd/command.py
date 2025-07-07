from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import click

from rdetoolkit import __version__
from rdetoolkit.cmd.default import INVOICE_JSON, PROPERTIES
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson, Properties
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)


class Command(click.Command):
    def __init__(self, name: str, **attrs: Any) -> None:
        super().__init__(name, **attrs)


class InitCommand:
    default_dirs = [
        Path("container/modules"),
        Path("container/data/inputdata"),
        Path("container/data/invoice"),
        Path("container/data/tasksupport"),
        Path("input/invoice"),
        Path("input/inputdata"),
        Path("templates/tasksupport"),
    ]

    def invoke(self) -> None:
        """Invokes the command and performs the necessary actions.

        Args:
            ctx (click.Context): The Click context object.

        Returns:
            None
        """
        try:
            self._info_msg("Ready to develop a structured program for RDE.")
            current_dir = Path.cwd()
            self.__make_dirs()
            self.__make_main_script(current_dir / "container" / "main.py")
            self.__make_requirements_txt(current_dir / "container" / "requirements.txt")
            self.__make_dockerfile(current_dir / "container" / "Dockerfile")
            # container
            self.__make_invoice_json(current_dir / "container" / "data" / "invoice" / "invoice.json")
            self.__make_template_json(current_dir / "container" / "data" / "tasksupport" / "invoice.schema.json")
            self.__make_metadata_def_json(current_dir / "container" / "data" / "tasksupport" / "metadata-def.json")
            # templates
            self.__make_template_json(current_dir / "templates" / "tasksupport" / "invoice.schema.json")
            self.__make_metadata_def_json(current_dir / "templates" / "tasksupport" / "metadata-def.json")
            # input
            self.__make_invoice_json(current_dir / "input" / "invoice" / "invoice.json")
            self._info_msg(f"\nCheck the folder: {current_dir}")
            self._success_msg("Done!")
        except Exception as e:
            logger.exception(e)
            self._error_msg("Failed to create files required for structured RDE programs.")
            raise click.Abort from e

    def __make_template_json(self, path: Path) -> None:
        if Path(path).exists():
            self._info_msg(f"Skip: {path} already exists.")
            return

        generator = InvoiceSchemaJsonGenerator(path)
        generator.generate()
        self._info_msg(f"Created: {path}")

    def __make_metadata_def_json(self, path: Path) -> None:
        if Path(path).exists():
            self._info_msg(f"Skip: {path} already exists.")
            return

        generator = MetadataDefJsonGenerator(path)
        generator.generate()
        self._info_msg(f"Created: {path}")

    def __make_invoice_json(self, path: Path) -> None:
        if Path(path).exists():
            self._info_msg(f"Skip: {path} already exists.")
            return

        generator = InvoiceJsonGenerator(path)
        generator.generate()
        self._info_msg(f"Created: {path}")

    def __make_dirs(self) -> None:
        for d in self.default_dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.exception(e)
                self._error_msg(f"Failed to create directory: {d}")
                raise click.Abort from e

    def __make_requirements_txt(self, path: Path) -> None:
        if Path(path).exists():
            self._info_msg(f"Skip: {path} already exists.")
            return

        generator = RequirementsTxtGenerator(path)
        generator.generate()
        self._info_msg(f"Created: {path}")

    def __make_main_script(self, path: Path) -> None:
        if Path(path).exists():
            self._info_msg(f"Skip: {path} already exists.")
            return
        generator = MainScriptGenerator(path)
        generator.generate()

    def __make_dockerfile(self, path: Path) -> None:
        if Path(path).exists():
            self._info_msg(f"Skip: {path} already exists.")
            return
        generator = DockerfileGenerator(path)
        generator.generate()
        self._info_msg(f"Created: {path}")

    def __delete_dirs(self) -> None:
        for d in self.default_dirs:
            if d.exists():
                shutil.rmtree(d)

    def _info_msg(self, msg: str) -> None:
        click.echo(msg)

    def _success_msg(self, msg: str) -> None:
        click.echo(click.style(msg, fg="green"))

    def _error_msg(self, msg: str) -> None:
        click.echo(click.style(f"Error! {msg}", fg="red"))


class VersionCommand:
    def invoke(self) -> None:
        """Invokes the command and prints the version number.

        Args:
            ctx (click.Context): The Click context object.

        Returns:
            None
        """
        click.echo(__version__)


class DockerfileGenerator:
    def __init__(self, path: str | Path = "Dockerfile"):
        self.path = path

    def generate(self) -> list[str]:
        """Generate a Dockerfile based on the specified path.

        Returns:
            list[str]: The content of the generated Dockerfile.
        """
        dockerfile_path = Path(self.path) if isinstance(self.path, str) else self.path

        contents = [
            "FROM python:3.11.9\n",
            "WORKDIR /app\n",
            "COPY requirements.txt .\n",
            "RUN pip install -r requirements.txt\n",
            "COPY main.py /app",
            "COPY modules/ /app/modules/\n",
        ]

        with open(dockerfile_path, "w", encoding="utf-8") as f:
            f.write("\n".join(contents))

        return contents


class RequirementsTxtGenerator:
    def __init__(self, path: str | Path = "requirements.txt"):
        self.path = path

    def generate(self) -> list[str]:
        """Generate a requirements.txt file based on the specified path.

        Returns:
            list[str]: The content of the generated requirements.txt file.
        """
        requirements_path = Path(self.path) if isinstance(self.path, str) else self.path

        contents = [
            "# ----------------------------------------------------",
            "# Please add the desired packages and install the libraries after that.",
            "# Then, run",
            "#",
            "# pip install -r requirements.txt",
            "#",
            "# on the terminal to install the required packages.",
            "# ----------------------------------------------------",
            "# ex.",
            "# pandas==2.0.3",
            "# numpy",
            f"rdetoolkit=={__version__}\n",
        ]

        with open(requirements_path, "w", encoding="utf-8") as f:
            f.write("\n".join(contents))

        return contents


class InvoiceSchemaJsonGenerator:
    def __init__(self, path: str | Path = "invoice.schema.json"):
        self.path = path

    def generate(self) -> dict[str, Any]:
        """Generate a invoice.schema.json file based on the specified path.

        Returns:
            dict[str, Any]: The content of the generated invoice.schema.json file.
        """
        invoice_schema_path = Path(self.path) if isinstance(self.path, str) else self.path

        obj = InvoiceSchemaJson(
            version="https://json-schema.org/draft/2020-12/schema",
            schema_id="https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
            description="RDEデータセットテンプレートテスト用ファイル",
            value_type="object",
            properties=Properties(),
        )
        cvt_obj = obj.model_dump(by_alias=True)
        cvt_obj["required"] = ["custom", "sample"]
        cvt_obj["properties"] = PROPERTIES

        with open(invoice_schema_path, mode="w", encoding="utf-8") as f:
            json.dump(cvt_obj, f, indent=4, ensure_ascii=False)

        return cvt_obj


class MetadataDefJsonGenerator:
    def __init__(self, path: str | Path = "metadata-def.json"):
        self.path = path

    def generate(self) -> dict[str, Any]:
        """Generate a metadata-def.json file based on the specified path.

        Returns:
            dict[str, Any]: The content of the metadata-def.json file.
        """
        matadata_def_path = Path(self.path) if isinstance(self.path, str) else self.path

        obj: dict[str, Any] = {}

        with open(matadata_def_path, mode="w", encoding="utf-8") as f:
            json.dump(obj, f, indent=4, ensure_ascii=False)

        return obj


class InvoiceJsonGenerator:
    def __init__(self, path: str | Path = "invoice.json"):
        self.path = path

    def generate(self) -> dict[str, Any]:
        """Generate a invoice.json file based on the specified path.

        Returns:
            dict[str, Any]: The content of the invoice.json file.
        """
        invoice_path = Path(self.path) if isinstance(self.path, str) else self.path

        with open(invoice_path, mode="w", encoding="utf-8") as f:
            json.dump(INVOICE_JSON, f, indent=4, ensure_ascii=False)

        return INVOICE_JSON


class MainScriptGenerator:
    def __init__(self, path: str | Path):
        self.path = path

    def generate(self) -> list[str]:
        """Generates a script template for the source code.

        Returns:
            list[str]: A list of strings representing the contents of the generated script.
        """
        main_path = Path(self.path) if isinstance(self.path, str) else self.path

        contents = [
            "# The following script is a template for the source code.\n",
            "import rdetoolkit\n",
            "rdetoolkit.workflows.run()\n",
        ]

        with open(main_path, "w", encoding="utf-8") as f:
            f.write("\n".join(contents))

        return contents
