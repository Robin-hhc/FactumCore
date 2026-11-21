/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08180(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
