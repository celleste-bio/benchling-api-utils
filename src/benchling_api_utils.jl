module BenchlingAPI

# packages
import Base64
import HTTP
import JSON
import SHA

# exports
export query
export create
export update
export dump

config_example = Dict{String, Any}(
    domain: "tenant.benchling.com",
    api_key: "sk_XXXXXXXXXXXXXXXX",
    project: "My Projects"
)

"""
encodes key for REST api authorization
using base64encode encoding
"""
function encode_key(key::String)::String
    key_encoded = "Basic $(Base64.base64encode(key)[1:end-1])6"
    return key_encoded
end

"""
send api request
"""
function api_request(url::String, auth_header::String, method::String; payload::String="")::HTTP.Response
    # send the request
    response = HTTP.request(
        method,
        url,
        headers = Dict(
            "Accept" => "application/json",
            "Authorization" => auth_header
        ),
        body = payload
    )
    # check the response
    if (method == "GET") && (response.status == 200)
        # Success
    elseif (method == "POST") && (response.status == 202 || response.status == 201 || response.status == 200)
        # Success
    elseif (method == "PATCH") && (response.status == 200)
        # Success
    else
        error("Request failed with status code $(response.status)")
    end

    return response
end

"""
merges nested dictionaries with similiar keys
"""
function merge_nested_dict(d1::Dict, d2::Dict)::Dict
    merged_dict = deepcopy(d1)
    for (key, value) in d2
        if key in keys(merged_dict)
            if isa(value, Dict) && isa(merged_dict[key], Dict)
                merged_dict[key] = merge_nested_dict(merged_dict[key], value)
            else
                merged_dict[key] = [merged_dict[key]; value]    
            end
        else
            merged_dict[key] = value
        end
    end
    return merged_dict
end

"""
query benchling
"""
function query(config, endpoint::String; kwargs...)::Dict
    kwargs = Dict(kwargs)

    next_token = "not a token"
    response_body = Dict()
    while next_token != ""
        if next_token == "not a token"
            next_token = ""  # Only in the first iteration
        end
        # set the authentication header with the correct API key
        auth_header = encode_key(config["benchling"]["api_key"])
        url = "https://$(config["benchling"]["domain"])/api/v2/$endpoint?"
        if next_token != ""
            url += "nextToken=$next_token"
        end

        if !isempty(kwargs)
            for (key, value) in kwargs
                url += "&$key=$value"
            end
        end

        response = api_request(url, auth_header, "GET")

        body_string = String(response.body)
        body_dict = JSON.parse(body_string)
        response_body = merge_nested_dict(response_body, body_dict)
        if haskey(body_dict, "nextToken")
            next_token = body_dict["nextToken"]
        end
    end

    return response_body
end

"""
create benchling
"""
function create(config, endpoint::String, payload::Dict{String, Any})::Nothing
    # set the authentication header with the correct API key
    auth_header = encode_key(config["benchling"]["api_key"])
    url = "https://$(config["benchling"]["domain"])/api/v2/$endpoint?"

    # convert payload to JSON string
    json_payload = JSON.json(payload)

    response = api_request(url, auth_header, "POST", payload=json_payload)
    # response_body = String(response.body)
    return nothing
end

"""
update benchling
"""
function update(config, endpoint::String, payload::Dict)
    # set the authentication header with the correct API key
    auth_header = encode_key(config["benchling"]["api_key"])
    url = "https://$(config["benchling"]["domain"])/api/v2/$endpoint?"

    # convert payload to JSON string
    json_payload = JSON.json(payload)

    response = api_request(url, auth_header, "PATCH", payload=json_payload)
    # response_body = String(response.body)
    # return response_body
end

function dump(config, endpoints::String[], dump_file::String)
    benchling_raw = Dict()
    for endpoint in endpoints
        raw_result = query_benchling(config, endpoint)
        benchling_raw = merge_nested_dict(benchling_raw, raw_result)
    end
    benchling_raw = merge_nested_dict(custom_entities_raw, mixtures_raw)
    json_dump = JSON.json(benchling_raw, 4)
    write(dump_file, json_dump)
end

"""
retrieves project id from benchling
"""
function get_project_id(config)::String
    projects_raw = query_benchling(config, "projects")
    
    project_id = ""
    for project in projects_raw["projects"]
        if project["name"] == config["benchling"]["project"]
            project_id = project["id"]
            break
        end
    end

    return project_id
end

"""
retrieves schema id from benchling
"""
function get_schema_id(config, schema_name::String)::String
    entity_schemas = query_benchling(config, "entity-schemas")
    
    schema_id = ""
    for schema in entity_schemas["entitySchemas"]
        if schema["name"] == schema_name
            schema_id = schema["id"]
            break
        end
    end

    return schema_id
end

"""
retrieves entity id from benchling
"""
function get_entity_id(config, entity_schema::String ,entity_name::String)::String
    schema_id = get_schema_id(config, entity_schema)
    entities = query_benchling(config, "custom-entities", schemaId=schema_id)
    
    entity_id = ""
    for entity in entities["customEntities"]
        if entity["name"] == entity_name
            entity_id = entity["id"]
            break
        end
    end

    return entity_id
end

"""
retrieves mixture id from benchling
"""
function get_mixture_id(config, mixture_schema::String ,mixture_name::String)::String
    schema_id = get_schema_id(config, mixture_schema)
    entities = query_benchling(config, "custom-entities", schemaId=schema_id)
    
    mixture_id = ""
    for mixture in entities["customEntities"]
        if mixture["name"] == mixture_name
            mixture_id = mixture["id"]
            break
        end
    end

    return mixture_id
end

"""
retrieves folder id from benchling
"""
function get_folder_id(config, folder_name::String)::String
    project_id = get_project_id(config)
    folders = query_benchling(config, "folders", projectId=project_id)
    
    folder_id = ""
    for folder in folders["folders"]
        if folder["name"] == folder_name
            folder_id = folder["id"]
            break
        end
    end

    return folder_id
end

"""
retrieves author id from benchling
"""
function get_user_id(config, author_name::String)::String
    project_id = get_project_id(config)
    authors = query_benchling(config, "users")
    
    author_id = ""
    for author in authors["users"]
        if author["name"] == author_name
            author_id = author["id"]
            break
        end
    end

    return author_id
end

function get_dropdown_option_id(config, dropdown_name, option)
    dropdowns = query_benchling(config, "dropdowns")
    dropdown_id = ""
    for dropdown in dropdowns["dropdowns"]
        if dropdown["name"] == dropdown_name
            dropdown_id = dropdown["id"]
        end
    end

    dropdown_list = query_benchling(config, "dropdowns/$dropdown_id")

    option_id = ""
    for element in dropdown_list["options"]
        if element["name"] == option
            option_id = element["id"]
        end
    end
    return option_id
end

function get_local_entity_id(entities, entity_name::String)::String
    entity_id = ""
    for entity in entities
        if entity["name"] == entity_name
            entity_id = entity["id"]
            break
        end
    end
    return entity_id
end

function get_local_dropdown_option_id(dropdown_list, option)
    option_id = ""
    for element in dropdown_list["options"]
        if element["name"] == option
            option_id = element["id"]
        end
    end
    return option_id
end

function get_field_definition(config, schema::String, field::String)::Dict
    schemas = query_benchling(config, "entity-schemas")
    for scm in schemas["entitySchemas"]
        if scm["name"] == schema
            for fld in scm["fieldDefinitions"]
                if fld["name"] == field
                    return fld
                end
            end
        end
    end
end

function chunk_payload(payload, chunk_size=2500)
    chunks = []
    for i in 1:chunk_size:length(payload)
        chunk = payload[i:min(i + chunk_size - 1, length(payload))]
        push!(chunks, chunk)
    end
    return chunks
end

end # module BenchlingAPI
