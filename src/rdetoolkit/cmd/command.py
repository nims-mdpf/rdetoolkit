from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import typer
import yaml
from tomlkit import document
from tomlkit.toml_file import TOMLFile

from rdetoolkit import __version__
from rdetoolkit.cmd.default import INVOICE_JSON, PROPERTIES
from rdetoolkit.models.invoice_schema import InvoiceSchemaJson, Properties
from rdetoolkit.rdelogger import get_logger

logger = get_logger(__name__)

_DATACLASS_KWARGS: dict[str, bool] = {"slots": True} if sys.version_info >= (3, 10) else {}


class InitTemplateError(RuntimeError):
    """Raised when a user-provided init template cannot be applied."""


@dataclass(**_DATACLASS_KWARGS)
class InitTemplateConfig:
    entry_point: Optional[Path] = None
    modules: Optional[Path] = None
    tasksupport: Optional[Path] = None
    inputdata: Optional[Path] = None
    other: Optional[list[Path]] = None

    def has_templates(self) -> bool:
        """Return True if any template path is defined."""
        return any(
            (
                self.entry_point,
                self.modules,
                self.tasksupport,
                self.inputdata,
                self.other,
            ),
        )


class InitTemplateLoader:
    """Load template definitions for the init command."""

    SUPPORTED_FILENAMES = ("pyproject.toml", "rdeconfig.yaml", "rdeconfig.yml")

    def __init__(self, template_path: Path) -> None:
        self.template_path = template_path

    def load(self) -> InitTemplateConfig:
        """Load template configuration from a TOML or YAML file."""
        config_file = self._resolve_template_file()
        init_section, section_label = self._extract_init_section(config_file)
        base_dir = config_file.parent
        config = InitTemplateConfig(
            entry_point=self._resolve_path(
                init_section,
                "entry_point",
                base_dir,
                config_file,
                allow_file=True,
                allow_dir=False,
                required_description="a file",
            ),
            modules=self._resolve_path(
                init_section,
                "modules",
                base_dir,
                config_file,
                allow_file=True,
                allow_dir=True,
            ),
            tasksupport=self._resolve_path(
                init_section,
                "tasksupport",
                base_dir,
                config_file,
                allow_file=True,
                allow_dir=True,
            ),
            inputdata=self._resolve_path(
                init_section,
                "inputdata",
                base_dir,
                config_file,
                allow_file=False,
                allow_dir=True,
                required_description="a directory",
            ),
            other=self._resolve_path_list(
                init_section,
                "other",
                base_dir,
                config_file,
                allow_file=True,
                allow_dir=True,
            ),
        )
        if not config.has_templates():
            emsg = f"No valid template entries were found under {section_label} in {config_file}"
            raise InitTemplateError(emsg)
        return config

    def _resolve_template_file(self) -> Path:
        if self.template_path.is_file():
            if self.template_path.name not in self.SUPPORTED_FILENAMES:
                supported = ", ".join(self.SUPPORTED_FILENAMES)
                emsg = f"--template expects one of ({supported}). Got: {self.template_path.name}"
                raise InitTemplateError(emsg)
            return self.template_path.resolve()
        if self.template_path.is_dir():
            for name in self.SUPPORTED_FILENAMES:
                candidate = self.template_path / name
                if candidate.exists():
                    return candidate.resolve()
            supported = ", ".join(self.SUPPORTED_FILENAMES)
            emsg = f"Could not find any of ({supported}) under {self.template_path}"
            raise InitTemplateError(emsg)
        emsg = f"Template path must be a file or directory. Got: {self.template_path}"
        raise InitTemplateError(emsg)

    def _extract_init_section(self, config_file: Path) -> tuple[Mapping[str, Any], str]:
        if config_file.name == "pyproject.toml":
            toml = TOMLFile(str(config_file))
            document = toml.read()
            raw = document.unwrap()
            init_section = raw.get("tool", {}).get("rdetoolkit", {}).get("init")
            label = "[tool.rdetoolkit.init]"
        else:
            with open(config_file, encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                emsg = f"{config_file} must be a mapping in order to define init templates."
                raise InitTemplateError(emsg)
            init_section = loaded.get("init")
            label = "init"
        if not isinstance(init_section, Mapping):
            emsg = f"{label} section was not found in {config_file}"
            raise InitTemplateError(emsg)
        return init_section, label

    def _resolve_path(
        self,
        section: Mapping[str, Any],
        key: str,
        base_dir: Path,
        config_file: Path,
        *,
        allow_file: bool,
        allow_dir: bool,
        required_description: Optional[str] = None,
    ) -> Optional[Path]:
        raw_value = section.get(key)
        if raw_value is None:
            return None
        if not isinstance(raw_value, str) or not raw_value.strip():
            emsg = f"The '{key}' value inside {config_file} must be a non-empty string."
            raise InitTemplateError(emsg)
        candidate = Path(raw_value).expanduser()
        candidate = (base_dir / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not candidate.exists():
            emsg = f"Template path for '{key}' does not exist: {candidate}"
            raise InitTemplateError(emsg)
        if candidate.is_file() and allow_file:
            if required_description == "a directory":
                emsg = f"The '{key}' template must reference {required_description}. Got file: {candidate}"
                raise InitTemplateError(emsg)
            return candidate
        if candidate.is_dir() and allow_dir:
            if required_description == "a file":
                emsg = f"The '{key}' template must reference {required_description}. Got directory: {candidate}"
                raise InitTemplateError(emsg)
            return candidate
        expected = required_description or "a file or directory"
        emsg = f"The '{key}' template must reference {expected}. Got: {candidate}"
        raise InitTemplateError(emsg)

    def _resolve_path_list(
        self,
        section: Mapping[str, Any],
        key: str,
        base_dir: Path,
        config_file: Path,
        *,
        allow_file: bool,
        allow_dir: bool,
    ) -> Optional[list[Path]]:
        raw_value = section.get(key)
        if raw_value is None:
            return None
        values: list[Any]
        if isinstance(raw_value, str):
            values = [raw_value]
        elif isinstance(raw_value, list):
            values = raw_value
        else:
            emsg = f"The '{key}' value inside {config_file} must be a string or list of strings."
            raise InitTemplateError(emsg)
        resolved: list[Path] = []
        for item in values:
            if not isinstance(item, str) or not item.strip():
                emsg = f"Each '{key}' entry inside {config_file} must be a non-empty string."
                raise InitTemplateError(emsg)
            resolved_path = self._resolve_path(
                {key: item},
                key,
                base_dir,
                config_file,
                allow_file=allow_file,
                allow_dir=allow_dir,
            )
            if resolved_path:
                resolved.append(resolved_path)
        return resolved


class Command:
    """Legacy command base class - no longer needed with Typer but kept for compatibility."""

    def __init__(self, name: str, **attrs: Any) -> None:
        """Initialize command (legacy compatibility)."""
        self.name = name
        self.attrs = attrs


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

    def __init__(
        self,
        template_path: Optional[Path] = None,
        cli_template_config: Optional[InitTemplateConfig] = None,
    ) -> None:
        self.template_path = template_path
        self.cli_template_config = cli_template_config

    def invoke(self) -> None:
        """Create the boilerplate layout for developing RDE structured programs."""
        try:
            self._info_msg("Ready to develop a structured program for RDE.")
            current_dir = Path.cwd()
            template_config = self.__merge_template_configs(
                self.__load_template_config(), self.cli_template_config,
            )
            if self.cli_template_config and self.cli_template_config.has_templates():
                self.__persist_cli_templates(self.cli_template_config)
            self.__make_dirs()
            main_script_path = current_dir / "container" / "main.py"
            if template_config and template_config.entry_point:
                self.__copy_entry_point_template(template_config.entry_point, main_script_path)
            else:
                self.__make_main_script(main_script_path)
            self.__make_requirements_txt(current_dir / "container" / "requirements.txt")
            self.__make_dockerfile(current_dir / "container" / "Dockerfile")
            modules_dir = current_dir / "container" / "modules"
            if template_config and template_config.modules:
                self.__populate_from_template(template_config.modules, modules_dir)
            # container
            self.__make_invoice_json(current_dir / "container" / "data" / "invoice" / "invoice.json")
            container_tasksupport_dir = current_dir / "container" / "data" / "tasksupport"
            template_tasksupport_dir = current_dir / "templates" / "tasksupport"
            if template_config and template_config.tasksupport:
                self.__apply_directory_template(
                    template_config.tasksupport,
                    [container_tasksupport_dir, template_tasksupport_dir],
                )
            else:
                self.__make_template_json(container_tasksupport_dir / "invoice.schema.json")
                self.__make_metadata_def_json(container_tasksupport_dir / "metadata-def.json")
                # templates
                self.__make_template_json(template_tasksupport_dir / "invoice.schema.json")
                self.__make_metadata_def_json(template_tasksupport_dir / "metadata-def.json")
            container_inputdata_dir = current_dir / "container" / "data" / "inputdata"
            input_inputdata_dir = current_dir / "input" / "inputdata"
            if template_config and template_config.inputdata:
                self.__apply_directory_template(
                    template_config.inputdata,
                    [container_inputdata_dir, input_inputdata_dir],
                )
            if template_config and template_config.other:
                self.__apply_other_templates(template_config.other, current_dir / "container")
            # templates
            # input
            self.__make_invoice_json(current_dir / "input" / "invoice" / "invoice.json")
            self._info_msg(f"\nCheck the folder: {current_dir}")
            self._success_msg("Done!")
        except InitTemplateError as e:
            logger.exception(e)
            self._error_msg(str(e))
            raise typer.Abort from e
        except Exception as e:
            logger.exception(e)
            self._error_msg("Failed to create files required for structured RDE programs.")
            raise typer.Abort from e

    def __load_template_config(self) -> Optional[InitTemplateConfig]:
        if self.template_path is None:
            return None
        loader = InitTemplateLoader(self.template_path)
        return loader.load()

    def __persist_cli_templates(self, cli_templates: InitTemplateConfig) -> None:
        if not cli_templates.has_templates():
            return
        config_path, filetype = self.__determine_config_path()
        if filetype == "toml":
            self.__write_pyproject_init(config_path, cli_templates)
        else:
            self.__write_yaml_init(config_path, cli_templates)

    def __determine_config_path(self) -> tuple[Path, str]:
        cwd = Path.cwd()
        pyproject = cwd / "pyproject.toml"
        rdeconfig_yaml = cwd / "rdeconfig.yaml"
        rdeconfig_yml = cwd / "rdeconfig.yml"
        if pyproject.exists():
            return pyproject, "toml"
        if rdeconfig_yaml.exists():
            return rdeconfig_yaml, "yaml"
        if rdeconfig_yml.exists():
            return rdeconfig_yml, "yaml"
        return pyproject, "toml"

    def __write_pyproject_init(self, path: Path, templates: InitTemplateConfig) -> None:
        toml_file = TOMLFile(str(path))
        doc = toml_file.read() if path.exists() else document()
        tool_section_raw: Any = doc.get("tool")
        tool_section: dict[str, Any] = dict(tool_section_raw) if isinstance(tool_section_raw, Mapping) else {}
        rde_section_raw: Any = tool_section.get("rdetoolkit")
        rde_section: dict[str, Any] = dict(rde_section_raw) if isinstance(rde_section_raw, Mapping) else {}
        init_existing_raw: Any = rde_section.get("init")
        init_table: dict[str, Any] = dict(init_existing_raw) if isinstance(init_existing_raw, Mapping) else {}
        self.__assign_config_entries(init_table, templates)
        rde_section["init"] = init_table
        tool_section["rdetoolkit"] = rde_section
        doc["tool"] = tool_section
        toml_file.write(doc)

    def __write_yaml_init(self, path: Path, templates: InitTemplateConfig) -> None:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        init_raw: Any = data.get("init")
        init_section: dict[str, Any] = dict(init_raw) if isinstance(init_raw, Mapping) else {}
        self.__assign_config_entries(init_section, templates)
        data["init"] = init_section
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def __assign_config_entries(self, target: dict[str, Any], templates: InitTemplateConfig) -> None:
        if templates.entry_point:
            target["entry_point"] = self.__format_path_for_config(templates.entry_point)
        if templates.modules:
            target["modules"] = self.__format_path_for_config(templates.modules)
        if templates.tasksupport:
            target["tasksupport"] = self.__format_path_for_config(templates.tasksupport)
        if templates.inputdata:
            target["inputdata"] = self.__format_path_for_config(templates.inputdata)
        if templates.other:
            target["other"] = [self.__format_path_for_config(p) for p in templates.other]

    def __format_path_for_config(self, path: Path) -> str:
        cwd = Path.cwd()
        try:
            return path.relative_to(cwd).as_posix()
        except ValueError:
            return path.as_posix()

    def __merge_template_configs(
        self,
        base: Optional[InitTemplateConfig],
        override: Optional[InitTemplateConfig],
    ) -> Optional[InitTemplateConfig]:
        if override is None or not override.has_templates():
            return base
        merged = base or InitTemplateConfig()
        if override.entry_point:
            merged.entry_point = override.entry_point
        if override.modules:
            merged.modules = override.modules
        if override.tasksupport:
            merged.tasksupport = override.tasksupport
        if override.inputdata:
            merged.inputdata = override.inputdata
        if override.other:
            merged.other = override.other
        return merged

    def __copy_entry_point_template(self, source: Path, destination: Path) -> None:
        if destination.exists():
            self._info_msg(f"Skip: {destination} already exists.")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self._info_msg(f"Created from template: {destination}")

    def __apply_directory_template(self, source: Path, destinations: list[Path]) -> None:
        for dest in destinations:
            self.__populate_from_template(source, dest)

    def __apply_other_templates(self, sources: list[Path], container_dir: Path) -> None:
        for source in sources:
            destination = container_dir / source.name if source.is_dir() else container_dir
            self.__populate_from_template(source, destination)

    def __populate_from_template(self, source: Path, destination: Path) -> None:
        if source.resolve() == destination.resolve():
            self._info_msg(f"Skip: source and destination are identical for {source}")
            return
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
            self._info_msg(f"Populated {destination} from template directory: {source}")
            return

        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination / source.name)
        self._info_msg(f"Copied template file {source} into {destination}")

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
                raise typer.Abort from e

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
        typer.echo(msg)

    def _success_msg(self, msg: str) -> None:
        typer.echo(typer.style(msg, fg=typer.colors.GREEN))

    def _error_msg(self, msg: str) -> None:
        typer.echo(typer.style(f"Error! {msg}", fg=typer.colors.RED))


class VersionCommand:
    def invoke(self) -> None:
        """Print the installed RDEToolKit version."""
        typer.echo(__version__)


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

        obj = InvoiceSchemaJson(  # type: ignore[call-arg]
            version="https://json-schema.org/draft/2020-12/schema",
            schema_id="https://rde.nims.go.jp/rde/dataset-templates/dataset_template_custom_sample/invoice.schema.json",
            description="RDEデータセットテンプレートテスト用ファイル",
            value_type="object",
            properties=Properties(custom=None, sample=None),
            required=None,
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
