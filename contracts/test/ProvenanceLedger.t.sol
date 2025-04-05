// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Test, console2} from "forge-std/Test.sol";
import {ProvenanceLedger} from "../src/ProvenanceLedger.sol";

contract ProvenanceLedgerTest is Test {
    ProvenanceLedger public ledger;
    address public owner; // Contract deployer/owner
    address public user1; // Simulated end-user address 1
    address public user2; // Simulated end-user address 2
    address public nonOwner; // An address that is not the contract owner

    // Sample data
    string constant DATASET_TYPE = "DATASET";
    string constant MODEL_TYPE = "MODEL";
    string constant SAMPLE_CID_1 = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";
    string constant SAMPLE_CID_2 = "bafybeicgmdpaltqszsvsemdqv3vgdrzttanzx3fuzsyuk5li6iomymqrw4";
    string constant METADATA_CID = "bafybeihdwdgytgswsgjl4fxblbftuoylcrkhxvhbavhukp6jw4ileh3nqi";

    // Event signature for testing event emission
    event AssetRegistered(
        address indexed owner,
        uint256 timestamp,
        string indexed assetType,
        string filecoinCid
    );

    function setUp() public {
        owner = address(this); // Test contract itself can be the owner for simplicity
        user1 = makeAddr("user1");
        user2 = makeAddr("user2");
        nonOwner = makeAddr("nonOwner");

        // Deploy the contract, setting the test contract as the initial owner
        ledger = new ProvenanceLedger(owner);
    }

    // =========================
    // Deployment Tests
    // =========================
    function test_DeploymentSetsOwner() public {
        assertEq(ledger.owner(), owner, "Deployment failed: Owner not set correctly.");
    }

    // =========================
    // Registration Tests
    // =========================
    function test_OwnerCanRegisterAsset() public {
        // Expect the event to be emitted with correct parameters
        // We don't check timestamp exactly due to block variability
        vm.expectEmit(true, true, true, true);
        emit AssetRegistered(user1, block.timestamp, DATASET_TYPE, SAMPLE_CID_1);

        // Register as owner, on behalf of user1
        ledger.registerAsset(
            user1,
            DATASET_TYPE,
            "Diabetes Dataset",
            "Sample dataset for prediction",
            SAMPLE_CID_1,
            METADATA_CID,
            "" // No source for a dataset
        );

        // Verify record exists and data is correct
        assertTrue(ledger.cidRegistered(SAMPLE_CID_1), "Registration failed: CID not marked as registered.");
        ProvenanceLedger.AssetRecord memory record = ledger.getAssetByCid(SAMPLE_CID_1);
        assertEq(record.owner, user1, "Record owner mismatch.");
        assertEq(record.assetType, DATASET_TYPE, "Record assetType mismatch.");
        assertEq(record.filecoinCid, SAMPLE_CID_1, "Record filecoinCid mismatch.");
        assertEq(record.metadataCid, METADATA_CID, "Record metadataCid mismatch.");
        assertTrue(record.exists, "Record exists flag is false.");

        // Verify owner mapping
        string[] memory ownedCids = ledger.getAssetsByOwner(user1);
        assertEq(ownedCids.length, 1, "Incorrect number of assets for user1.");
        assertEq(ownedCids[0], SAMPLE_CID_1, "Incorrect CID listed for user1.");
    }

    function test_RevertIf_NonOwnerRegistersAsset() public {
        // Change the caller to be a non-owner address
        vm.prank(nonOwner);
        // Expect revert due to onlyOwner modifier (simplest check)
        vm.expectRevert();
        // Alternatively, check for the specific string message:
        // vm.expectRevert(bytes("Ownable: caller is not the owner"));
        ledger.registerAsset(
            user1,
            DATASET_TYPE,
            "Dataset Name",
            "Description",
            SAMPLE_CID_1,
            METADATA_CID,
            ""
        );
    }

    function test_RevertIf_RegisteringEmptyCid() public {
        vm.expectRevert("CID cannot be empty");
        ledger.registerAsset(user1, DATASET_TYPE, "Name", "Desc", "", METADATA_CID, "");
    }

    function test_RevertIf_RegisteringDuplicateCid() public {
        // Register the first time (successfully)
        ledger.registerAsset(user1, DATASET_TYPE, "Name", "Desc", SAMPLE_CID_1, METADATA_CID, "");

        // Expect revert on the second attempt
        vm.expectRevert("CID already registered");
        ledger.registerAsset(user2, MODEL_TYPE, "Name2", "Desc2", SAMPLE_CID_1, "meta2", "source1");
    }

     function test_RevertIf_RegisteringWithZeroAddressOwner() public {
        vm.expectRevert("Owner address cannot be zero");
        ledger.registerAsset(address(0), DATASET_TYPE, "Name", "Desc", SAMPLE_CID_1, METADATA_CID, "");
    }

    // =========================
    // Query Tests
    // =========================
    function test_GetAssetByCid_CorrectData() public {
        // Register first
        ledger.registerAsset(user1, DATASET_TYPE, "DS Name", "DS Desc", SAMPLE_CID_1, METADATA_CID, "");

        // Query and assert
        ProvenanceLedger.AssetRecord memory record = ledger.getAssetByCid(SAMPLE_CID_1);
        assertEq(record.owner, user1);
        assertEq(record.assetType, DATASET_TYPE);
        assertEq(record.name, "DS Name");
        assertEq(record.description, "DS Desc");
        assertEq(record.metadataCid, METADATA_CID);
        assertTrue(record.timestamp > 0);
        assertTrue(record.exists);
    }

    function test_GetAssetByCid_RevertIf_NotFound() public {
        vm.expectRevert("CID not found");
        ledger.getAssetByCid(SAMPLE_CID_1); // Try to get non-existent CID
    }

    function test_GetAssetsByOwner_CorrectData() public {
        // Register two assets for user1
        ledger.registerAsset(user1, DATASET_TYPE, "", "", SAMPLE_CID_1, "", "");
        ledger.registerAsset(user1, MODEL_TYPE, "", "", SAMPLE_CID_2, METADATA_CID, SAMPLE_CID_1);
        // Register one asset for user2
        ledger.registerAsset(user2, DATASET_TYPE, "", "", "some_other_cid", "", "");

        // Query for user1
        string[] memory ownedCidsUser1 = ledger.getAssetsByOwner(user1);
        assertEq(ownedCidsUser1.length, 2, "Incorrect number of assets for user1.");
        assertEq(ownedCidsUser1[0], SAMPLE_CID_1, "First CID mismatch for user1.");
        assertEq(ownedCidsUser1[1], SAMPLE_CID_2, "Second CID mismatch for user1.");

         // Query for user2
        string[] memory ownedCidsUser2 = ledger.getAssetsByOwner(user2);
        assertEq(ownedCidsUser2.length, 1, "Incorrect number of assets for user2.");
        assertEq(ownedCidsUser2[0], "some_other_cid", "CID mismatch for user2.");
    }

    function test_GetAssetsByOwner_EmptyIf_NoAssets() public {
        string[] memory ownedCids = ledger.getAssetsByOwner(user1);
        assertEq(ownedCids.length, 0, "Should return empty array for owner with no assets.");
    }

} 