-- Define a module table
local api_utils = {}

local mime = require("mime")
local http = require("ssl.https")
local ltn12 = require("ltn12")
local json = require("dkjson")

config_example = {
    domain = "tenant.benchling.com",
    api_key = "sk_XXXXXXXXXXXXXXXX",
    auth_type = "api_key", -- OR "oauth"
    project = "My Projects"
}

-- Function to encode credentials
local function encode_key(str)
    local key_encoded = "Basic " .. mime.b64(str)
    return key_encoded
end

-- URL-encode a string
local function url_encode(url)
    if type(url) ~= "string" then
        error("Unsupported type given")
    end
    local encoded_url = url:gsub("\n", "\r\n")
    encoded_url = encoded_url:gsub(
        "([^%w%-_%.%~])",
        function(c)
            return string.format("%%%02X", string.byte(c))
        end
    )
    
    return encoded_url
end

local function length(containable)
    local cnt

    if type(containable) == "string" then
        cnt = #containable
    elseif type(containable) == "table" then
        cnt = 0
        for _, _ in pairs(containable) do
            cnt = cnt + 1
        end
    else
        error("Unsupported type given")
    end

    return cnt
end

-- Merge two arrays into one
local function merge_nested_tables(a, b)
    local result = {}
    local index = 1

    -- Copy all elements from the first table 'a' to 'result'
    for i = 1, length(a) do
        result[index] = a[i]
        index = index + 1
    end

    -- Copy all elements from the second table 'b' to 'result'
    for i = 1, length(b) do
        result[index] = b[i]
        index = index + 1
    end

    return result
end

-- Converts kebab-case to camelCase
local function kebab_to_camel_case(str)
    local result = ""
    local capitalize_next = false

    for i = 1, length(str) do
        local char = str:sub(i, i)
        if char == "-" then
            capitalize_next = true
        else
            result = result .. (capitalize_next and char:upper() or char)
            capitalize_next = false
        end
    end

    return result
end

-- Send api request
local function api_request(url, credentials, method, payload, auth_type)
    local response = {}
    local auth_header

    if auth_type == "oauth" then
        auth_header = "Bearer " .. credentials
    else
        -- Default = API key
        auth_header = encode_key(credentials)
    end

    local success, status_code, headers, status_text = http.request{
        url = url,
        method = method,
        headers = {
            ["Accept"] = "application/json",
            ["Authorization"] = auth_header,
            ["Content-Type"] = payload and "application/json" or nil
        },
        body = payload,
        sink = ltn12.sink.table(response)
    }

    if not success then
        error("Request failed")
    end

    local response_content = json.decode(table.concat(response))
    return response_content
end

-- Handles paginated API requests with optional endpoint parameters
local function paginated_api_request(base_url, credentials, method, payload, endpoint_key, kwargs, auth_type)
    local response_body = {}
    local next_token = ""

    repeat
        local url = base_url
        local endpoint_params = {}

        if next_token ~= "" then
            table.insert(endpoint_params, "nextToken=" .. next_token)
        end

        if kwargs then
            for key, value in pairs(kwargs) do
                table.insert(endpoint_params, url_encode(key) .. "=" .. url_encode(value))
            end
        end

        if #endpoint_params > 0 then
            url = url .. "?" .. table.concat(endpoint_params, "&")
        end

        local response_content = api_request(url, credentials, method, payload, auth_type)
        
        if response_content[endpoint_key] then
            response_body = merge_nested_tables(response_body, response_content[endpoint_key])
        else
            response_body = response_content
        end

        next_token = response_content["nextToken"] or ""
    until next_token == ""

    return response_body
end

local function request_with_pagination(config, endpoint, method, payload, version, kwargs)
    version = version or "v2"

    -- Auto-detect key for paginated result extraction
    local endpoint_key_map = {
        ["v2"] = kebab_to_camel_case(endpoint),
        ["v3-alpha"] = "items"
    }

    local endpoint_key = endpoint_key_map[version]
    local credentials = config["api_key"]
    local auth_type = config["auth_type"] or "api_key"

    local base_url = string.format("https://%s/api/%s/%s", config["domain"], version, endpoint)

    local response_body = paginated_api_request(
        base_url,
        credentials,
        method,
        payload and json.encode(payload) or nil,
        endpoint_key,
        kwargs,
        auth_type
    )

    return response_body
end

local function query(config, endpoint, kwargs, version)
    return request_with_pagination(config, endpoint, "GET", nil, version, kwargs)
end

local function create(config, endpoint, payload, version)
    return request_with_pagination(config, endpoint, "POST", payload, version, nil)
end

local function update(config, endpoint, payload, version)
    return request_with_pagination(config, endpoint, "PATCH", payload, version, nil)
end

-- Get OAuth2 token using client_credentials
local function get_oauth_token(domain, client_id, client_secret)
    local token_url = string.format("https://%s/api/v2/token", domain)
    local credentials = client_id .. ":" .. client_secret
    local auth_header = "Basic " .. mime.b64(credentials)

    local response = {}
    local body = "grant_type=client_credentials"

    local success, status_code, headers, status = http.request{
        url = token_url,
        method = "POST",
        headers = {
            ["Authorization"] = auth_header,
            ["Content-Type"] = "application/x-www-form-urlencoded",
            ["Content-Length"] = tostring(#body),
        },
        source = ltn12.source.string(body),
        sink = ltn12.sink.table(response)
    }

    if not success or status_code ~= 200 then
        error("OAuth token request failed")
    end

    local decoded = json.decode(table.concat(response))
    return decoded["access_token"]
end
 
api_utils.query = query
api_utils.create = create
api_utils.update = update
api_utils.get_oauth_token = get_oauth_token

-- Export the module
return api_utils
