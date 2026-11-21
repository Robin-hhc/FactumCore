/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05761(unsigned int count)
{
    const unsigned int limit = 88u;
    return count > limit ? limit : count;
}
