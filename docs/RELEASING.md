# Release checks

1. Run exact-source package, offline backend/controller/native tests and native wide/compact geometry checks. Verify upgrade/rollback separately and review the final diff; local checks are not live-action or hosted-CI proof.
2. Preserve the full license, required attribution and pinned donor/dataset provenance. Review optional previews for rights and private metadata; do not include private captures, credentials or raw provider/process logs.
3. Verify deterministic source-archive membership, modes, bytes and SHA256SUMS against the committed tree. Validate the extracted manifest and standalone operation. Exclude ignored backups and test artifacts from archives.
4. Preserve published Git history and existing tag targets. Runtime releases advance their single versioned path. A namespace change needs explicit enabled/menu/launcher reference updates and a backup; retain the stable preference path and rollback option.
5. Publish only with authorization for the concrete repository, tag/release and marketplace target. Read back the exact remote commit, hosted CI, tag target, release assets and deployed marketplace commit before reporting those outcomes. Do not restart the lock-hosting shell to hide stale QML.
