# config for a flask app

upstream zulu {
    # proxying to gunicorn running on localhost
	server 127.0.0.1:5000;
}

server {
	server_name zulu.example.com;
	root /path/to/www/zulu;
	index index.html;

        try_files  $uri/index.html $uri.html $uri @zulu;

        location @zulu {
	      proxy_set_header  X-Real-IP        $remote_addr;
	      proxy_set_header  X-Forwarded-For  $proxy_add_x_forwarded_for;
	      proxy_set_header  Host             $http_host;
	      proxy_redirect    off;
	      proxy_intercept_errors on;

	      # proxy cache config
	      client_max_body_size       10m;
	      client_body_buffer_size    256k;

	      proxy_buffer_size          32k;
	      proxy_buffers              8 64k;
	      proxy_busy_buffers_size    128k;
	      proxy_temp_file_write_size 128k;

	      proxy_cache zulu-cache;
              proxy_cache_valid  200 302  10s;
              proxy_cache_valid  404      10s;
	      proxy_cache_key         "$scheme$host$request_uri";

	      # the line below will bypass and cache requests with the header
	      # X-Whattup-Yo
	      # See http://wiki.nginx.org/HttpProxyModule#proxy_cache_bypass
	      # and http://wiki.nginx.org/HttpCoreModule#.24http_HEADER
	      proxy_cache_bypass $http_something_secret;

	      # next line should keep us from having stampeding herd problems
	      proxy_cache_use_stale updating error timeout;

	      proxy_pass        http://zulu;
        }
        error_page   500 502 503 504  /500.html;
        location = /500.html {
                 root /path/to/www/zulu;
        }
        error_page   404  /404.html;
        location = /404.html {
                 root /path/to/www/zulu;
        }

        # rewrites can go here
        # rewrite ^/old.html /new/file.html permanent;
}
