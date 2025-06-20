import abc
from abc import ABC, abstractmethod
from pathlib import Path
from rdetoolkit.models.rde2types import RawFiles as RawFiles, UnZipFilesPathList as UnZipFilesPathList, ZipFilesPathList as ZipFilesPathList

class IInputFileHelper(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    def get_zipfiles(self, input_files: list[Path]) -> ZipFilesPathList: ...
    @abstractmethod
    def unpacked(self, zipfile: Path, target_dir: Path) -> UnZipFilesPathList: ...

class IInputFileChecker(ABC, metaclass=abc.ABCMeta):
    @property
    @abstractmethod
    def checker_type(self) -> str: ...
    @abstractmethod
    def parse(self, src_input_path: Path) -> tuple[RawFiles, Path | None]: ...

class ICompressedFileStructParser(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    def read(self, zipfile: Path, target_path: Path) -> list[tuple[Path, ...]]: ...

class IArtifactPackageCompressor(ABC, metaclass=abc.ABCMeta):
    @property
    @abstractmethod
    def exclude_patterns(self) -> list[str]: ...
    @abstractmethod
    def archive(self, output_zip: str | Path) -> list[Path]: ...
