local_dir ?= minio_local_data

.PHONY: minio-local
minio-local:
	([ -d $(local_dir) ] || mkdir $(local_dir)) && docker run -d --name minio -p 9000:9000 -p 9001:9001 -v ./$(local_dir):/data minio/minio server /data --console-address ":9001"
