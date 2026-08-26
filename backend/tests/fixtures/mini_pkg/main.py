"""Main module that imports from the same package."""

from mini_pkg.lib import helper


def main() -> int:
    return helper(21)


if __name__ == "__main__":
    print(main())
