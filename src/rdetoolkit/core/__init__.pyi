from typing import Optional

class ManagedDirectory:
    """Directory manager that handles index-based subdirectories.

    This class manages a directory structure that can include indexed subdirectories
    under a 'divided' folder. The directory path is constructed as:
    - For idx=0: {base_dir}/{dirname}
    - For idx>0: {base_dir}/divided/{idx:0{n_digit}d}/{dirname}

    Example:
        >>> dir = ManagedDirectory("/path/to/base", "docs")
        >>> dir.path  # "/path/to/base/docs"
        >>> dir2 = dir(1)  # Creates "/path/to/base/divided/0001/docs"
    """

    path: str
    idx: int

    def __init__(self, base_dir: str, dirname: str, n_digit: Optional[int] = None, idx: Optional[int] = None) -> None: ...
    def create(self) -> None:
        """Create the managed directory if it doesn't exist.

        Raises:
            OSError: If directory creation fails
        """
        ...

    def list(self) -> list[str]:
        """List all files and directories in the managed directory.

        Returns:
            List[str]: List of paths as strings

        Raises:
            FileNotFoundError: If the directory does not exist
            OSError: If reading the directory fails
        """
        ...

    def __call__(self, idx: int) -> "ManagedDirectory":
        """Create a new ManagedDirectory instance with the specified index.

        Args:
            idx: Index for the new directory

        Returns:
            ManagedDirectory: New instance with the specified index

        Raises:
            ValueError: If idx is negative
            OSError: If directory creation fails
        """
        ...

class DirectoryOps:
    """Utility class for managing multiple directories with support for indexed subdirectories.

    This class provides functionality to:
    - Create and manage base directories
    - Create indexed subdirectories under a 'divided' folder
    - Access directories via attribute-style notation

    Example:
        >>> ops = DirectoryOps("/path/to/base")
        >>> ops.invoice  # Creates "/path/to/base/invoice"
        >>> ops.all(2)   # Creates base dirs and divided/0001, divided/0002 subdirs
    """

    def __init__(self, base_dir: str, n_digit: Optional[int] = None) -> None: ...
    def __getattr__(self, name: str) -> ManagedDirectory: ...
    def all(self, idx: Optional[int] = None) -> list[str]:
        """Create all supported directories and optionally their indexed subdirectories.

        When idx is specified, creates indexed subdirectories under 'divided' folder
        for supported directory types.

        Args:
            idx: Maximum index for divided subdirectories

        Returns:
            List[str]: List of created directory paths

        Raises:
            ValueError: If idx is negative
            OSError: If directory creation fails
        """
        ...

def resize_image_aspect_ratio(input_path: str, output_path: str, width: int, height: int) -> None: ...
def detect_encoding(path: str) -> str: ...
def read_from_json_file(path: str) -> str: ...
