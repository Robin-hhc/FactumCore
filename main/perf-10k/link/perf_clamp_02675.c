/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02675(unsigned int count)
{
    const unsigned int limit = 165u;
    return count > limit ? limit : count;
}
