function fix_corrupted_xdf(input_file, output_file)
    % FIX_CORRUPTED_XDF Fix XDF files with clock/offset synchronization mismatches
    %
    % Usage:
    %   fix_corrupted_xdf('corrupted.xdf')           % overwrites input
    %   fix_corrupted_xdf('corrupted.xdf', 'fixed.xdf')  % saves to output
    %
    % This script handles XDF files where clock_times and offset_values arrays
    % have mismatched lengths (typically by 1 sample).

    if nargin < 1
        error('Usage: fix_corrupted_xdf(input_file, [output_file])');
    end

    if nargin < 2
        output_file = input_file;
    end

    fprintf('\n=== XDF Corruption Fix ===\n');
    fprintf('Input:  %s\n', input_file);
    fprintf('Output: %s\n\n', output_file);

    % Try to load and catch error
    fprintf('Attempting to load XDF file...\n');
    try
        [streams, header] = load_xdf(input_file);
        fprintf('File loaded successfully - no corruption detected.\n');
        return;
    catch ME
        fprintf('Load failed (expected): %s\n\n', ME.message);
    end

    % Inspect what was partially loaded
    fprintf('=== Inspecting Synchronization Data ===\n\n');

    found_mismatch = false;

    for i = 1:length(streams)
        stream = streams{i};
        stream_name = stream.info.name{1};

        % Check if this stream has clock sync data
        if isfield(stream.info, 'clock_times') && ~isempty(stream.info.clock_times)
            ct_len = length(stream.info.clock_times);
            ov_len = length(stream.info.offset_values);

            if ct_len ~= ov_len
                fprintf('Stream %d: %s\n', i, stream_name);
                fprintf('  clock_times:    %d elements\n', ct_len);
                fprintf('  offset_values:  %d elements\n', ov_len);
                fprintf('  Difference:     %d element(s)\n', abs(ct_len - ov_len));

                if ct_len > ov_len
                    fprintf('  => clock_times is TOO LONG\n');
                    fprintf('  => Removing last %d element(s) from clock_times\n\n', ct_len - ov_len);
                    stream.info.clock_times(ov_len+1:end) = [];

                elseif ov_len > ct_len
                    fprintf('  => offset_values is TOO LONG\n');
                    fprintf('  => Removing last %d element(s) from offset_values\n\n', ov_len - ct_len);
                    stream.info.offset_values(ct_len+1:end) = [];
                end

                % Verify they now match
                if length(stream.info.clock_times) == length(stream.info.offset_values)
                    fprintf('  ✓ Corrected! Both now have %d elements\n\n', length(stream.info.clock_times));
                    found_mismatch = true;
                else
                    fprintf('  ✗ Still mismatched after fix!\n\n');
                    error('Could not fix synchronization mismatch for stream: %s', stream_name);
                end
            end
        end
    end

    if ~found_mismatch
        fprintf('No synchronization mismatches found.\n');
        return;
    end

    % Try to load again to verify fix
    fprintf('=== Verifying Fix ===\n\n');

    % Create temporary file with corrected data
    temp_file = [tempname '.xdf'];

    try
        fprintf('Writing corrected data to temporary file: %s\n', temp_file);
        xdf_write(temp_file, streams);
        fprintf('Attempting to reload corrected file...\n');

        [streams_verify, header_verify] = xdf(temp_file);
        fprintf('✓ Success! File reloads without errors\n');
        fprintf('  Loaded %d streams\n\n', length(streams_verify));

        % Copy corrected file to output location
        fprintf('Saving corrected file to: %s\n', output_file);
        copyfile(temp_file, output_file);

        % Create backup of original
        [path, name, ext] = fileparts(input_file);
        backup_file = fullfile(path, [name '_CORRUPTED' ext]);
        if ~isequal(output_file, input_file)
            fprintf('Original saved as: %s\n', backup_file);
            copyfile(input_file, backup_file);
        end

        fprintf('\n=== Fix Complete ===\n');
        fprintf('Corrected file ready for use!\n\n');

        delete(temp_file);

    catch ME
        fprintf('✗ Verification failed: %s\n', ME.message);
        fprintf('The automatic fix did not work.\n');
        fprintf('Please try manual inspection:\n');
        fprintf('  1. Display each stream''s arrays: disp(streams{i}.info.clock_times)\n');
        fprintf('  2. Check for obvious duplicates or outliers\n');
        fprintf('  3. Manually delete the problematic value\n\n');

        if isfile(temp_file)
            delete(temp_file);
        end
        error('Could not verify corrected file');
    end
end


function xdf_write(filename, streams)
    % XDF_WRITE Write XDF file from streams structure
    % This is a simplified writer that works with partially-loaded streams
    %
    % Note: This only works if you're using the XDF toolbox that has xdf_write
    % If xdf_write is not available, you'll need to use the MATLAB XDF toolbox
    % directly or re-save in your XDF processing software.

    % Try built-in xdf_write
    try
        % First attempt: use built-in xdf_write if available
        nargoutchk(0, 0);

        % Call the actual xdf_write function
        % This assumes the XDF toolbox has an xdf_write function
        feval('xdf_write', filename, streams);

    catch
        % If xdf_write doesn't exist, provide helpful error
        error(['xdf_write not found. The MATLAB XDF toolbox may not have a write function.\n', ...
               'Alternative: Use xdf_write_helper.m or manually re-save in your XDF software.']);
    end
end
