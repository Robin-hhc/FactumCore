/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03989(unsigned int count)
{
    const unsigned int limit = 93u;
    return count > limit ? limit : count;
}
