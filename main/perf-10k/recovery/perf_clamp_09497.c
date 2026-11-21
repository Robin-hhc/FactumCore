/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09497(unsigned int count)
{
    const unsigned int limit = 105u;
    return count > limit ? limit : count;
}
