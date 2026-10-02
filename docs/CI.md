# Compile Prismelier with GitHub Actions

## Setup required before the first successful run

`.github/workflows/compile.yml` invokes the **actual official Monkey C compiler** for
`fr265` and uploads its `.prg` only after compilation succeeds. It is a manual
workflow for a dedicated, officially provisioned Linux runner. Adding the workflow
alone does not install a runner or provide Garmin's device profiles.

The first CI build is still outstanding; see the [validation status](STATUS.md) for local build and simulator results.
Preflight and Python source/asset checks are not compilation.

### Why a pre-provisioned runner?

Garmin's official [setup guide](https://developer.garmin.com/connect-iq/connect-iq-basics/getting-started/)
uses SDK Manager, Garmin login, and a separate device download. A public SDK ZIP
contains the compiler but does **not** contain the FR265 device profile. No
Garmin-documented headless profile installer was found as of 1 October 2026.

The workflow does not use community containers that redistribute Garmin profiles,
upload SDK/profile archives to GitHub, or put Garmin account credentials in CI.
See Garmin's [developer agreement](https://developer.garmin.com/connect-iq/sdk/),
particularly the Program Materials restrictions. SDK use remains subject to it.

## Security boundary

GitHub [recommends against self-hosted runners for public repositories](https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners).
A runner executes repository code and any compromise can expose the local signing
key or other accessible data. **Do not register your everyday computer for this
public repository.** Use a dedicated isolated build machine/VM with no personal
files, production credentials, or sensitive network access. Prefer a clean,
single-job runner that is destroyed after use. Registration is a separate owner
setup decision; this project does not register or configure one automatically.

The committed workflow adds these limits; they are defense in depth, not a sandbox:

- Only manual `workflow_dispatch`; no push, PR, `pull_request_target`, or `workflow_run`
- Only the repository owner (including reruns), only `bensonlee5/prismelier`, only `refs/heads/main`
- A dedicated `prismelier-fr265` runner label, not a general-purpose runner
- Checkout of the triggering commit SHA, with persisted Git credentials disabled
- Read-only repository permission; only GitHub-maintained actions pinned to commit SHAs
- No credentials in GitHub secrets and no new key generation
- Exact artifact allowlist; no SDK, profiles, signing key, caches, or raw watch logs
- A 15-minute job timeout and a 14-day artifact retention period

Review all code and workflow changes before manually running main. Never approve
untrusted fork code for this runner or add an automatic PR trigger. Protect runner
access independently; future workflow edits can otherwise change these limits.

## Provision the dedicated runner

Do this yourself, or explicitly authorize the computer access and runner
registration separately. A runner registration establishes ongoing GitHub access.

1. Prepare an isolated **Ubuntu Linux x64** environment. Garmin documents Ubuntu
   for Linux SDK support. Install Java 11+ and Python 3.10+ using trusted sources.
   Pillow is optional, but enables the font/AOD/texture visual-asset checks
2. Download [Garmin SDK Manager](https://developer.garmin.com/connect-iq/sdk/), review
   its agreement, and sign in through its own interface
3. Install **Connect IQ SDK 9.2.0** and **Forerunner 265**. Do this under the same
   local OS user that will run the job. Check that
   `~/.Garmin/ConnectIQ/Devices/fr265/compiler.json` exists
4. Configure an existing RSA-4096 DER developer key outside the checkout. Keep a
   private backup. If you need a new key, generate one deliberately using Garmin's
   extension; this workflow does not generate one. Keep Garmin login sessions and
   unrelated credentials out of the runner's execution environment
5. Export **local runner environment variables** `CIQ_SDK` (SDK directory) and
   `CIQ_KEY` (absolute path to the local key) before starting its runner process.
   Do not enter the key contents into a repository variable, workflow file, log,
   secret or artifact. Restart an existing runner process after changing its
   environment
6. Follow GitHub's [runner setup instructions](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)
   at **Settings → Actions → Runners → New self-hosted runner**. Add the custom
   label **prismelier-fr265**. The workflow also requires `linux` and `x64`
7. From a local checkout under that same OS user, run
   `python3 tools/ci_build.py preflight`. It must pass before starting a CI run

The compiler JAR is pinned by SHA-256 to the official Linux SDK 9.2.0 archive:

- Archive: `connectiq-sdk-lin-9.2.0-2026-06-09-92a1605b2.zip`
- [Official download](https://developer.garmin.com/downloads/connect-iq/sdks/connectiq-sdk-lin-9.2.0-2026-06-09-92a1605b2.zip)
- Archive SHA-256: `4907d8455b651c5a00a865e364cc4f1921c055b9279c7c8634c7a7a6773b5593`
- `bin/monkeybrains.jar` SHA-256: `b9be696349c91feec3fb9723584daf624421d197f76ff86f72c7b3f66492fc9f`

These hashes were computed from Garmin's download on 1 October 2026; they are not
Garmin-issued signed checksums. Changing the SDK requires reviewing and updating
`tools/ci_build.py`. The device profile's aggregate content hash is recorded for
every build and must stay unchanged throughout compilation. This fingerprint does
not authenticate the profile. The JAR pin does not authenticate the launcher, Java
runtime, or other SDK files; official provisioning remains necessary. SDK Manager can update profiles independently, so matching the SDK
version alone does not guarantee byte-identical builds. Preserve the same
privately installed inputs and signing key when reproducing a result; never
redistribute Garmin's profile files through the repository or artifacts.

## Run and download

1. Open [Actions → Compile Forerunner 265](https://github.com/bensonlee5/prismelier/actions/workflows/compile.yml)
2. Choose **Run workflow**, leave the branch as **main**, and start it as the owner
3. Wait for **Compile and sign the actual FR265 program** and artifact upload to
   finish successfully. A queued job usually means no matching runner is online;
   a skipped job means the owner/main/repository guard rejected the dispatch
4. Open the run summary and download **Prismelier-fr265-<commit SHA>-<run ID>-<attempt>** from Artifacts
   while signed into GitHub. Downloads expire after 14 days
5. Extract the ZIP. It contains `Prismelier.prg`, `SHA256SUMS`, and `build-info.json`.
   On Linux, `sha256sum -c SHA256SUMS` verifies the downloaded files
6. Test the program in Garmin's simulator and follow the [USB loading guide](INSTALL.md)

Only a newly produced, nonempty PRG from an exit-code-zero compiler run is staged.
The record includes the commit, compiler/profile fingerprints, program size and
SHA-256. Successful compilation establishes that the source/resources compile for
FR265. It does not establish simulator behavior, graphics-pool fit under load,
weather synchronization, hardware reliability or battery life.

## Common failures

- **No matching runner:** bring the isolated runner online and verify all four labels
- **Missing CIQ_SDK/CIQ_KEY:** export these in the runner process's local environment
- **Missing FR265 profile:** use SDK Manager under the runner's local user; installing
  the SDK ZIP alone is insufficient
- **Compiler hash/version differs:** install the pinned official version or review an
  intentional update; do not disable the check just to get a green run
- **Compiler errors:** fix the reported source/resource errors and run again. The
  workflow intentionally does not mark a failed or unavailable compile successful
