echo "Creating default S3 policies"
for policy in /tmp/scripts/*.json; do
    echo "Creating policy $$policy"
    mc --insecure admin policy create $minio_alias $$(basename $$policy .json) $$policy
    echo "Policy $$(basename $$policy .json) created"
done
