// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AuditAnchor
/// @notice Event only anchor for the Helm audit log. It stores nothing and holds no funds.
///         Only hashes are ever written, so no business data reaches the chain.
///         Anyone may call it, so verifiers must filter events by the expected sender
///         (the Helm anchor address) and then compare the hash with one recomputed from the database.
contract AuditAnchor {
    /// @param seq      id of the last audit log row covered by the anchor
    /// @param headHash sha256 hash of that row, which commits to every earlier row
    /// @param by       address that sent the anchor
    event Anchored(uint256 indexed seq, bytes32 headHash, address indexed by);

    /// @param version    owner cash policy version
    /// @param policyHash sha256 of the canonical policy at that version
    /// @param by         address that sent the anchor
    event PolicyAnchored(uint256 indexed version, bytes32 policyHash, address indexed by);

    function anchor(uint256 seq, bytes32 headHash) external {
        emit Anchored(seq, headHash, msg.sender);
    }

    function anchorPolicy(uint256 version, bytes32 policyHash) external {
        emit PolicyAnchored(version, policyHash, msg.sender);
    }
}
