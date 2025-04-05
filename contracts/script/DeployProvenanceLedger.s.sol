// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Script, console2} from "forge-std/Script.sol";
import {ProvenanceLedger} from "../src/ProvenanceLedger.sol";

contract DeployProvenanceLedger is Script {
    function run() external returns (ProvenanceLedger) {
        // Load deployment configuration from environment variables
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address initialOwner = vm.envAddress("INITIAL_CONTRACT_OWNER");

        // Validate required environment variables
        require(deployerPrivateKey != 0, "DEPLOYER_PRIVATE_KEY environment variable not set or invalid");
        require(initialOwner != address(0), "INITIAL_CONTRACT_OWNER environment variable not set or invalid");

        console2.log("Deploying ProvenanceLedger...");
        console2.log("Deployer Address:", vm.addr(deployerPrivateKey));
        console2.log("Initial Contract Owner:", initialOwner);

        // Start broadcasting transactions using the deployer's private key
        vm.startBroadcast(deployerPrivateKey);

        // Deploy the contract, passing the initial owner address to the constructor
        ProvenanceLedger ledger = new ProvenanceLedger(initialOwner);

        // Stop broadcasting
        vm.stopBroadcast();

        console2.log("ProvenanceLedger deployed successfully!");
        console2.log("Contract Address:", address(ledger));

        return ledger;
    }
} 