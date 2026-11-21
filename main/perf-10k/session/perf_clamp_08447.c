/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08447(unsigned int count)
{
    const unsigned int limit = 183u;
    return count > limit ? limit : count;
}
