// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title VisibilityProbe
/// @notice Minimal monotonic state probe for confirmed-state latency
///         measurement (protocol section 6, Listing 3).
/// @dev The probe measures the availability of *state*, not the arrival of a
///      receipt.  Each write carries a monotonic sequence number per key; a
///      read node is considered to have made the update visible once `read`
///      returns a sequence at least as large as the one submitted.  Keys are
///      per generator, so the monotonicity requirement never makes two
///      workstations conflict.
contract VisibilityProbe {
    mapping(bytes32 => uint256) private values;
    mapping(bytes32 => uint256) private sequences;

    event Updated(bytes32 indexed key, uint256 value, uint256 seq);

    /// @notice Record `value` under `key` with strictly increasing `seq`.
    function write(bytes32 key, uint256 value, uint256 seq) external {
        require(seq > sequences[key], "non-monotonic sequence");
        values[key] = value;
        sequences[key] = seq;
        emit Updated(key, value, seq);
    }

    /// @notice Return the current value and sequence of `key`.
    /// @dev Called with block_identifier = "latest" while the node runs with
    ///      allow-unfinalized-queries = false, so a returned sequence implies
    ///      accepted state.
    function read(bytes32 key) external view returns (uint256, uint256) {
        return (values[key], sequences[key]);
    }
}
