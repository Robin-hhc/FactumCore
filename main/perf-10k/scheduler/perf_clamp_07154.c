/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07154(unsigned int count)
{
    const unsigned int limit = 114u;
    return count > limit ? limit : count;
}
