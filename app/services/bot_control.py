import asyncio
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


@dataclass(frozen=True)
class GitUpdateResult:
    success: bool
    message: str
    details: str = ""


def is_github_bound(repo_url: str | None) -> bool:
    return bool(repo_url and repo_url.strip())


async def restart_current_process(delay_seconds: float = 1.5) -> None:
    await asyncio.sleep(delay_seconds)
    os.execv(sys.executable, [sys.executable, *sys.argv])


async def _run_command(args: list[str], *, timeout_seconds: int = 120) -> CommandResult:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=PROJECT_ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        output_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except TimeoutError:
        process.kill()
        output_bytes, _ = await process.communicate()
        output = output_bytes.decode("utf-8", errors="replace").strip()
        return CommandResult(
            returncode=-1,
            output=(output + "\nКоманда превысила лимит ожидания.").strip(),
        )

    output = output_bytes.decode("utf-8", errors="replace").strip()
    return CommandResult(returncode=process.returncode or 0, output=output)


async def _ensure_origin_remote(git_path: str, repo_url: str) -> GitUpdateResult | None:
    remote = await _run_command([git_path, "remote", "get-url", "origin"], timeout_seconds=30)

    if remote.returncode == 0:
        if remote.output.strip() == repo_url:
            return None

        updated = await _run_command([git_path, "remote", "set-url", "origin", repo_url], timeout_seconds=30)
        if updated.returncode != 0:
            return GitUpdateResult(
                success=False,
                message="Не удалось обновить remote origin для GitHub.",
                details=updated.output,
            )

        return None

    added = await _run_command([git_path, "remote", "add", "origin", repo_url], timeout_seconds=30)
    if added.returncode != 0:
        return GitUpdateResult(
            success=False,
            message="Не удалось добавить remote origin для GitHub.",
            details=added.output,
        )

    return None


async def _current_branch(git_path: str) -> str | None:
    branch = await _run_command([git_path, "rev-parse", "--abbrev-ref", "HEAD"], timeout_seconds=30)
    if branch.returncode != 0:
        return None

    value = branch.output.strip()
    if not value or value == "HEAD":
        return None

    return value


def _sanitize_details(details: str, repo_url: str | None) -> str:
    cleaned = details.strip()
    if repo_url:
        cleaned = cleaned.replace(repo_url, "[GitHub repo]")

    return cleaned[-3500:]


async def update_from_github(repo_url: str | None) -> GitUpdateResult:
    if not is_github_bound(repo_url):
        return GitUpdateResult(
            success=False,
            message="GitHub не привязан: в .env не указан GITHUB_REPO_URL.",
        )

    git_path = shutil.which("git")
    if git_path is None:
        return GitUpdateResult(
            success=False,
            message="Git не найден в PATH. Установи Git на сервере или добавь его в PATH.",
        )

    if not (PROJECT_ROOT / ".git").exists():
        return GitUpdateResult(
            success=False,
            message=(
                "Папка бота не является git-репозиторием. "
                "Для обновлений разверни бота через git clone или выполни первичную настройку Git в этой папке."
            ),
        )

    remote_error = await _ensure_origin_remote(git_path, repo_url.strip())
    if remote_error is not None:
        return GitUpdateResult(
            success=False,
            message=remote_error.message,
            details=_sanitize_details(remote_error.details, repo_url),
        )

    branch = await _current_branch(git_path)
    if branch:
        pull_args = [git_path, "pull", "--ff-only", "origin", branch]
    else:
        pull_args = [git_path, "pull", "--ff-only"]

    pulled = await _run_command(pull_args)
    details = _sanitize_details(pulled.output, repo_url)

    if pulled.returncode != 0:
        return GitUpdateResult(
            success=False,
            message="GitHub обновление не выполнено. Git вернул ошибку.",
            details=details,
        )

    return GitUpdateResult(
        success=True,
        message="Обновление из GitHub выполнено.",
        details=details,
    )
