// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

// Remove Test import if not actually a test file
// import "forge-std/Test.sol"; // Standard Foundry import
import "@openzeppelin/contracts/access/Ownable.sol"; // Import Ownable

/**
 * @title ProvenanceLedger
 * @notice A contract to record immutable provenance for AI assets stored on Filecoin.
 * @dev Uses CID strings as primary identifiers and maps them to asset metadata and owner.
 */
contract ProvenanceLedger is Ownable {

    // ==================
    // Structs
    // ==================

    struct AssetRecord {
        address owner;          // Wallet address of the user/backend registering the asset
        uint256 timestamp;      // Timestamp of registration (block.timestamp)
        string assetType;       // e.g., "DATASET", "MODEL", "METADATA"
        string name;            // User-defined name for the asset (optional)
        string description;     // User-defined description (optional)
        string filecoinCid;     // The primary Filecoin CID (from Lighthouse) - Key identifier
        string metadataCid;     // CID of associated metadata JSON file (optional)
        string sourceAssetCid;  // For models, CID of the source dataset (optional)
        bool exists;            // Flag to easily check if a record exists for a CID
    }

    // ==================
    // State Variables
    // ==================

    // Mapping from the primary Filecoin CID to its provenance record
    mapping(string => AssetRecord) public recordsByCid;

    // Mapping from an owner address to a list of CIDs they have registered
    mapping(address => string[]) public cidsByOwner;

    // Fee required for certain services (e.g., training, inference)
    uint256 public serviceFee = 100000000000000;

    // Optional: To easily check if a CID string has already been registered
    mapping(string => bool) public cidRegistered;

    // ==================
    // Events
    // ==================

    event AssetRegistered(
        address indexed owner,
        uint256 timestamp,
        string name,
        string assetType,
        string filecoinCid
    );

    event PaymentReceived(
        address indexed payer,
        uint256 amountPaid,
        string serviceType,     // e.g., "TRAINING", "INFERENCE"
        string paymentNonce     // Unique identifier provided by payer
    );

    // ==================
    // Constructor
    // ==================

    // Sets the initial owner to the deployer address
    // Use initialOwner for Ownable >= 5.0.0
    constructor(address initialOwner) Ownable(initialOwner) {}

    // ==================
    // Functions
    // ==================

    /**
     * @notice Registers provenance information for a new asset.
     * @dev Only callable by the contract owner (expected to be the backend service wallet).
     * @param ownerAddress The original user/owner initiating the action via the backend.
     * @param assetType Type of asset ("DATASET", "MODEL", etc.).
     * @param name Optional name for the asset.
     * @param description Optional description.
     * @param filecoinCid The primary Filecoin CID for the asset (must be unique).
     * @param metadataCid Optional CID for associated metadata.
     * @param sourceAssetCid Optional CID for the source asset (e.g., dataset for a model).
     */
    function registerAsset(
        address ownerAddress,
        string memory assetType,
        string memory name,
        string memory description,
        string memory filecoinCid,
        string memory metadataCid,
        string memory sourceAssetCid
    ) public onlyOwner { // Apply access control
        // Input Validation: Ensure CID is not empty and not already registered
        require(bytes(filecoinCid).length > 0, "CID cannot be empty");
        require(!cidRegistered[filecoinCid], "CID already registered");
        require(ownerAddress != address(0), "Owner address cannot be zero");

        // Create the record
        AssetRecord memory newRecord = AssetRecord({
            owner: ownerAddress,
            timestamp: block.timestamp,
            assetType: assetType,
            name: name,
            description: description,
            filecoinCid: filecoinCid,
            metadataCid: metadataCid,
            sourceAssetCid: sourceAssetCid,
            exists: true
        });

        // Store the record
        recordsByCid[filecoinCid] = newRecord;
        cidsByOwner[ownerAddress].push(filecoinCid);
        cidRegistered[filecoinCid] = true;

        // Emit the event
        emit AssetRegistered(ownerAddress, block.timestamp, name, assetType, filecoinCid);
    }

    /**
     * @notice Retrieves the full provenance record for a given Filecoin CID.
     * @param cid The Filecoin CID to query.
     * @return The AssetRecord struct associated with the CID.
     */
    function getAssetByCid(string memory cid) public view returns (AssetRecord memory) {
        require(cidRegistered[cid], "CID not found");
        return recordsByCid[cid];
    }

    /**
     * @notice Retrieves the list of Filecoin CIDs registered by a specific owner address.
     * @param owner The address of the owner to query.
     * @return An array of Filecoin CIDs registered by the owner.
     */
    function getAssetsByOwner(address owner) public view returns (string[] memory) {
        return cidsByOwner[owner];
    }

    // ===========================
    // Fee and Payment Functions
    // ===========================

    /**
     * @notice Sets the required fee for payable services.
     * @dev Only callable by the contract owner.
     * @param _newFee The new service fee in wei.
     */
    function setServiceFee(uint256 _newFee) public onlyOwner {
        serviceFee = _newFee;
    }

    /**
     * @notice Allows a user to pay the required service fee.
     * @dev Requires sending the exact `serviceFee` amount.
     * @param _serviceType Identifier for the service being paid for (e.g., "TRAINING").
     * @param _paymentNonce A unique identifier for this specific payment attempt (provided by frontend).
     */
    function payForService(
        string memory _serviceType, 
        string memory _paymentNonce
    ) public payable {
        require(msg.value == serviceFee, "Incorrect payment amount sent");
        require(bytes(_serviceType).length > 0, "Service type cannot be empty");
        require(bytes(_paymentNonce).length > 0, "Payment nonce cannot be empty");

        // Emit an event to make payment verification easier off-chain
        emit PaymentReceived(msg.sender, msg.value, _serviceType, _paymentNonce);

        // Note: The contract now holds the received funds.
        // Add withdrawal logic if needed (e.g., onlyOwner withdraw pattern).
    }

    /**
     * @notice Allows the owner to withdraw accumulated service fees.
     * @dev Only callable by the contract owner.
     */
    function withdrawFees() public onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No fees to withdraw.");
        payable(owner()).transfer(balance);
    }
} 