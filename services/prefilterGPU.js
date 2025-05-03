function prefilteredGPUs(gpuList, conditions) {
    const filteredGPUs = gpuList.filter(gpu => {
        return Object.keys(conditions).every(key => {
            // Check if the condition exists in the user input
            if (conditions[key]) {
                if (key === 'country' || key === 'region' || key === 'operating_system') {
                    // Ensure the key exists in the GPU object before comparing
                    if (gpu[key]) {
                        return gpu[key].toLowerCase() === conditions[key].toLowerCase();
                    }
                    return false; // Return false if key doesn't exist in GPU data
                }
            }
            return true; // If the condition is not present, no filtering is applied for that key
        });
    });

    console.log(filteredGPUs.slice(0, 5)); // Log the first 5 filtered GPUs for debugging
    console.log(filteredGPUs.length); // Log the total number of filtered GPUs for debugging
    

    return filteredGPUs.slice(0, 5);
}

module.exports = {
    prefilteredGPUs
};
